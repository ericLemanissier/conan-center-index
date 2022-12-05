# pylint: disable = invalid-name,too-few-public-methods

import os
import json
import asyncio
import logging
from datetime import datetime
from typing import Dict, Set, Any
import yaml
import requests
import aiohttp
import packaging.version


class MatrixGenerator:
    owner: str = "conan-io"
    repo: str = "conan-center-index"
    dry_run: bool = False

    def __init__(self, token: str = "", user: str = "", pw: str = ""):  # noqa: MC0001
        self.session = requests.session()
        if token:
            self.session.headers["Authorization"] = f"token {token}"

        self.session.headers["Accept"] = "application/vnd.github.v3+json"
        self.session.headers["User-Agent"] = "request"

        self.session.auth = None
        if user and pw:
            self.session.auth = requests.auth.HTTPBasicAuth(user, pw)

        self.prs: Dict[int, Dict[str, Any]] = {}

        page = 1
        while True:
            results = self._make_request("GET", f"/repos/{self.owner}/{self.repo}/pulls", params={
                "state": "open",
                "sort": "created",
                "direction": "desc",
                "per_page": 100,
                "page": str(page)
            }).json()
            for p in results:
                if int(p["number"]) in [13539, ]:
                    logging.warning("ignoring pr #%s because it is in deny list", p["number"])
                    continue
                body = p["body"] or ""
                if "bsd" in p["title"].lower() or "bsd" in body.lower():
                    self.prs[int(p["number"])] = p
            page += 1
            if not results:
                break

        for pr_number, pr in self.prs.items():
            pr["libs"] = self._get_modified_libs_for_pr(pr_number)

    async def generate_matrix(self) -> None:  # noqa: MC0001
        res = []
        async with aiohttp.ClientSession() as session:

            async def _add_package(package: str, repo: str, ref: str, pr: str = "0") -> None:
                version = packaging.version.Version("0.0.0")
                folder = ""
                async with session.get(f"https://raw.githubusercontent.com/{repo}/{ref}/recipes/{package}/config.yml") as r:
                    if r.status == 404:
                        return
                    r.raise_for_status()
                    config = yaml.safe_load(await r.text())
                    for v in config["versions"]:
                        try:
                            tmpver = packaging.version.Version(v)
                            if tmpver > version:
                                version = tmpver
                                folder = config["versions"][v]["folder"]
                        except packaging.version.InvalidVersion:
                            logging.warning("Error parsing version %s for package %s in pr %s", v, package, pr)
                if folder:
                    res.append({'package': package,
                                'version': str(version),
                                'repo': repo,
                                'ref': ref,
                                'folder': folder,
                                'pr': pr})
            tasks = []
            # for package in  r.json():
            #     tasks.append(asyncio.create_task(_add_package(package['name'], '%s/%s' % (self.owner, self.repo), 'master')))

            for pr in self.prs.values():
                pr_number = str(pr["number"])
                for package in pr['libs']:
                    if not pr["head"]["repo"]:
                        logging.warning("no repo detected for pr #%s", pr_number)
                        continue
                    tasks.append(_add_package(package, pr["head"]["repo"]["full_name"], pr["head"]["ref"], pr_number))

            await asyncio.gather(*tasks)

        with open("matrix.yml", "w", encoding="latin_1") as f:
            json.dump({"include": res}, f)

    def _get_modified_libs_for_pr(self, pr: int) -> Set[str]:
        res = set()
        for file in self._make_request("GET", f"/repos/{self.owner}/{self.repo}/pulls/{pr}/files").json():
            parts = file["filename"].split("/")
            if len(parts) >= 2 and parts[0] == "recipes":
                res.add(parts[1])
        return res

    def _make_request(self, method: str, url: str, **kwargs) -> requests.Response:
        if self.dry_run and method in ["PATCH", "POST"]:
            return requests.Response()

        r = self.session.request(method, f"https://api.github.com{url}", **kwargs)
        r.raise_for_status()
        if int(r.headers["X-RateLimit-Remaining"]) < 10:
            logging.warning("%s/%s github api call used, remaining %s until %s",
                            r.headers["X-Ratelimit-Used"], r.headers["X-RateLimit-Limit"], r.headers["X-RateLimit-Remaining"],
                            datetime.fromtimestamp(int(r.headers["X-Ratelimit-Reset"])))
        return r


def main() -> None:
    d = MatrixGenerator(token=os.getenv("GH_TOKEN", ""))
    asyncio.run(d.generate_matrix())


if __name__ == "__main__":
    # execute only if run as a script
    main()
