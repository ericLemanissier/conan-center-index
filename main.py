#pylint: disable = missing-module-docstring, missing-class-docstring, missing-function-docstring, invalid-name, line-too-long, too-few-public-methods

import os
import json
import asyncio
import logging
import yaml
import requests
import aiohttp
import packaging.version

class MatrixGenerator:
    owner = "conan-io"
    repo = "conan-center-index"

    def __init__(self, token=None, user=None, pw=None):
        self.session = requests.session()
        self.session.headers = {}
        if token:
            self.session.headers["Authorization"] = f"token {token}"

        self.session.headers["Accept"] = "application/vnd.github.v3+json"
        self.session.headers["User-Agent"] = "request"

        self.session.auth = None
        if user and pw:
            self.session.auth = requests.auth.HTTPBasicAuth(user, pw)

        self.prs = {}

        page = 1
        while True:
            r = self.session.request("GET", f"https://api.github.com/repos/{self.owner}/{self.repo}/pulls", params={
                "state": "open",
                "sort": "created",
                "direction": "desc",
                "per_page": 100,
                "page": str(page)
            })
            r.raise_for_status()
            results = r.json()
            for p in results:
                if int(p["number"]) in [13539,]:
                    logging.warning("ignoring pr #%s because it is in deny list", p["number"])
                    continue
                body = p["body"] or ""
                if "bsd" in p["title"].lower() or "bsd" in body.lower():
                    self.prs[int(p["number"])] = p
            page += 1
            if not results:
                break

        async def _populate_diffs():
            async with aiohttp.ClientSession() as session:
                async def _populate_diff(pr):
                    async with session.get(self.prs[pr]["diff_url"]) as r:
                        r.raise_for_status()
                        self.prs[pr]["libs"] = set()
                        try:
                            diff = await r.text()
                        except UnicodeDecodeError:
                            logging.warning("error when decoding diff at %s", self.prs[pr]["diff_url"])
                            return
                        for line in diff.split("\n"):
                            if line.startswith("+++ b/recipes/") or line.startswith("--- a/recipes/"):
                                self.prs[pr]["libs"].add(line.split("/")[2])
                await asyncio.gather(*[asyncio.create_task(_populate_diff(pr)) for pr in self.prs])

        loop = asyncio.get_event_loop()
        loop.run_until_complete(_populate_diffs())

    async def generate_matrix(self):
        res = []
        async with aiohttp.ClientSession() as session:

            async def _add_package(package, repo, ref, pr = "0"):
                version = packaging.version.Version("0.0.0")
                folder = ""
                async with session.get(f"https://raw.githubusercontent.com/{repo}/{ref}/recipes/{package}/config.yml") as r:
                    if r.status  == 404:
                        return
                    r.raise_for_status()
                    config = yaml.safe_load(await r.text())
                    for v in config["versions"]:
                        try:
                            tmpVer = packaging.version.Version(v)
                            if tmpVer > version:
                                version = tmpVer
                                folder = config["versions"][v]["folder"]
                        except packaging.version.InvalidVersion:
                            logging.warning("Error parsing version %s for package %s in pr %s", v, package, pr)
                if folder:
                    res.append({
                            'package': package,
                            'version': str(version),
                            'repo': repo,
                            'ref': ref,
                            'folder': folder,
                            'pr': pr,
                        })
            tasks = []
           # for package in  r.json():
           #     tasks.append(asyncio.create_task(_add_package(package['name'], '%s/%s' % (self.owner, self.repo), 'master')))

            for pr in self.prs.values():
                pr_number = str(pr["number"])
                for package in pr['libs']:
                    if not pr["head"]["repo"]:
                        logging.warning("no repo detected for pr #%s", pr_number)
                        continue
                    tasks.append(asyncio.create_task(_add_package(package, pr["head"]["repo"]["full_name"], pr["head"]["ref"], pr_number)))

            await asyncio.gather(*tasks)


        with open("matrix.yml", "w", encoding="latin_1") as f:
            json.dump({"include": res}, f)




def main():
    d = MatrixGenerator(token=os.getenv("GH_TOKEN"))
    loop = asyncio.get_event_loop()
    loop.run_until_complete(d.generate_matrix())


if __name__ == "__main__":
    # execute only if run as a script
    main()
