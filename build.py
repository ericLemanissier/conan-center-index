import os
import yaml
import json
import asyncio


async def process_ref(package):
    config_file = os.path.join(package, "config.yml")
    if not os.path.isfile(config_file):
        return
    if package in ["bacnet-stack", "b2", "ncurses"]:
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
            print("error during conan export %s %s: %s" % (os.path.join(package, folder), ref, p.returncode))
            continue
        if os.path.isfile(conandata_full_path):
            if os.path.isfile(conandata_path):
                os.remove(conandata_path)
            os.rename(conandata_full_path, conandata_path)

        p = await asyncio.create_subprocess_exec("conan", "info", ref, "--json", "info.json")
        await p.wait()
        if p.returncode == 6:
            print("ignoring invalid package %s" % ref)
            continue
        elif p.returncode == 1:
            print("missing binary requirement of %s ?" % ref)
            continue
        if p.returncode != 0:
            print("error during conan info %s: %s" % (ref, p.returncode))
            continue

        with open("info.json", "r") as stream:
            infos = json.load(stream)
        if any([info["id"] == "INVALID" for info in infos]):
            print("ingoring invalid package %s" % ref)
            continue
        for info in infos:
            if info["reference"] + "@" == ref:
                id = info["id"]

        if any(["deprecated" in info for info in infos]):
            print("skipping %s because it is deprecated" % ref)
            continue

        p = await asyncio.create_subprocess_exec("conan", "search", ref, "--revisions", "--json", "revision.json")
        await p.wait()

        if p.returncode != 0:
            print("error during conan search %s --revisions --json revision.json: %s" % (ref, p.returncode))
            continue
        with open("revision.json", "r") as stream:
            revisions = json.load(stream)
        if len(revisions) == 0:
            rev = ""
        elif len(revisions) == 1:
            rev = revisions[0]["revision"]
        else:
            print("unexpected revisions for %s: %s" % (ref, revisions))

        fullref = "%s#%s" % (ref, rev)

        p = await asyncio.create_subprocess_exec("conan", "search", fullref, "-r", "all", "--json", "binaries.json")
        await p.wait()

        if p.returncode != 0:
            print("error during conan search %s -r all --json binaries.json: %s" % (fullref, p.returncode))
            continue
        with open("binaries.json", "r") as stream:
            binaries = json.load(stream)
        assert not binaries["error"]
        if any([p["id"] == id for r in binaries["results"] for i in r["items"] for p in i["packages"]]):
            continue
        print("no binaries for %s" % fullref)

        p = await asyncio.create_subprocess_exec("conan", "install", fullref, "-b", package)
        await p.wait()
        if p.returncode == 1:
            print("error while building %s, ignored" % ref)
            continue

        if p.returncode != 0:
            print("error during conan install %s -b %s: %s" % (fullref, package, p.returncode))
            continue
        p = await asyncio.create_subprocess_exec("conan", "test", os.path.join(package, folder, "test_package", "conanfile.py"), fullref)
        await p.wait()
        if p.returncode == 1:
            print("Test of %s failed" % ref)
            continue
        if p.returncode != 0:
            print("error during conan test %s %s: %s" % (os.path.join(package, folder, "test_package", "conanfile.py"), fullref, p.returncode))
            continue
        p = await asyncio.create_subprocess_exec("conan", "upload", fullref, "--all")
        await p.wait()
        if p.returncode != 0:
            print("error during conan upload %s --all: %s" % (fullref, p.returncode))
            continue

os.chdir("CCI")
os.chdir("recipes")

import asyncio

async def main():

    for filename in os.scandir():
        if not filename.is_dir():
            continue
        package = filename.name
        asyncio.create_task(process_ref(package))
        await asyncio.sleep(0)


asyncio.run(main())
