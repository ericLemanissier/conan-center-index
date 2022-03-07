import os
import yaml
import json
import asyncio
import logging
import sys
import re

sem = asyncio.Semaphore(1)

async def process_ref(package):
    if package in ["bacnet-stack", "b2", "ncurses"]:
        return
    global sem
    async with sem:
        config_file = os.path.join(package, "config.yml")
        if not os.path.isfile(config_file):
            logging.error("no config file for %s", package)
            return
        with open(config_file, "r") as stream:
            config = yaml.safe_load(stream)
        for version in config["versions"]:
            folder = config["versions"][version]["folder"]
            conandata_path = os.path.join(os.path.join(package, folder), "conandata.yml")
            conandata_full_path = os.path.join(os.path.join(package, folder), "conandata_full.yml")
            if os.path.isfile(conandata_path):
                if os.path.isfile(conandata_full_path):
                    os.remove(conandata_full_path)
                os.rename(conandata_path, conandata_full_path)
                with open(conandata_full_path, "r") as stream:
                    conandata_yml = yaml.safe_load(stream)
                info = {}
                for entry in conandata_yml:
                    if version not in conandata_yml[entry]:
                        continue
                    info[entry] = {}
                    info[entry][version] = conandata_yml[entry][version]
                with open(conandata_path, "w") as stream:
                    yaml.safe_dump(info, default_flow_style=False, stream=stream)
            ref = "%s/%s@" % (package, version)
            p = await asyncio.create_subprocess_exec("conan", "export", os.path.join(package, folder), ref)
            await p.wait()
            if p.returncode != 0:
                logging.error("error during conan export %s %s: %s", os.path.join(package, folder), ref, p.returncode)
                continue
            if os.path.isfile(conandata_full_path):
                if os.path.isfile(conandata_path):
                    os.remove(conandata_path)
                os.rename(conandata_full_path, conandata_path)

            info_file = os.path.join(package, "info.json")
            p = await asyncio.create_subprocess_exec("conan", "info", ref, "--json", info_file, "-o", "glib:with_elf=False")
            await p.wait()
            if p.returncode == 6:
                logging.info("ignoring invalid package %s", ref)
                continue
            elif p.returncode == 1:
                logging.error("missing binary requirement of %s ?", ref)
                continue
            if p.returncode != 0:
                logging.error("error during conan info %s: %s", ref, p.returncode)
                continue

            with open(info_file, "r") as stream:
                infos = json.load(stream)
            os.remove(info_file)
            if any([info["id"] == "INVALID" for info in infos]):
                logging.info("ingoring invalid package %s", ref)
                continue
            id = None
            for info in infos:
                if info["reference"] + "@" == ref:
                    id = info["id"]
            if not id:
                logging.error("could not find %s in %s",ref, infos)
                exit(-3)

            if any(["deprecated" in info for info in infos]):
                logging.info("skipping %s because it is deprecated", ref)
                continue

            revision_file = os.path.join(package, "revision.json")
            p = await asyncio.create_subprocess_exec("conan", "search", ref, "--revisions", "--json", revision_file)
            await p.wait()

            if p.returncode != 0:
                logging.error("error during conan search %s --revisions --json %s: %s", ref, revision_file, p.returncode)
                continue
            with open(revision_file, "r") as stream:
                revisions = json.load(stream)
            os.remove(revision_file)
            if len(revisions) == 0:
                rev = ""
            elif len(revisions) == 1:
                rev = revisions[0]["revision"]
            else:
                logging.error("unexpected revisions for %s: %s", ref, revisions)

            fullref = "%s#%s" % (ref, rev)

            binaries_file = os.path.join(package, "binaries.json")
            p = await asyncio.create_subprocess_exec("conan", "search", fullref, "-r", "all", "--json", binaries_file)
            await p.wait()

            if p.returncode != 0:
                logging.error("error during conan search %s -r all --json %s: %s", fullref, binaries_file, p.returncode)
                continue
            with open(binaries_file, "r") as stream:
                binaries = json.load(stream)
            os.remove(binaries_file)
            assert not binaries["error"]
            if any([p["id"] == id for r in binaries["results"] for i in r["items"] for p in i["packages"]]):
                continue
            logging.info("no binaries for %s", fullref)

            p = await asyncio.create_subprocess_exec("conan", "install", fullref, "-b", package, "-o", "glib:with_elf=False")
            await p.wait()
            if p.returncode == 1:
                logging.error("error while building %s, ignored", ref)
                continue

            if p.returncode != 0:
                logging.error("error during conan install %s -b %s: %s", fullref, package, p.returncode)
                continue
            p = await asyncio.create_subprocess_exec("conan", "test", os.path.join(package, folder, "test_package", "conanfile.py"), fullref, "-o", "glib:with_elf=False")
            await p.wait()
            if p.returncode == 1:
                logging.error("Test of %s failed", ref)
                continue
            if p.returncode != 0:
                logging.error("error during conan test %s %s: %s", os.path.join(package, folder, "test_package", "conanfile.py"), fullref, p.returncode)
                continue
            p = await asyncio.create_subprocess_exec("conan", "upload", fullref, "--all")
            await p.wait()
            if p.returncode != 0:
                logging.error("error during conan upload %s --all: %s", fullref, p.returncode)
                continue

if __name__ == "__main__":
    os.chdir("CCI")
    os.chdir("recipes")
    loop = asyncio.get_event_loop()
    pattern = re.compile(sys.argv[1] if len(sys.argv) >= 2 else ".*")
    async def main():
        await asyncio.gather(*[asyncio.create_task(process_ref(filename.name)) for filename in os.scandir() if filename.is_dir() and pattern.match(filename.name)])
    loop.run_until_complete(main())
