import os
import yaml
import json
import subprocess

os.chdir("CCI")
os.chdir("recipes")

for filename in os.scandir():
    if not filename.is_dir():
        continue
    package = filename.name
    config_file = os.path.join(package, "config.yml")
    if not os.path.isfile(config_file):
        continue
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
        p = subprocess.run(["conan", "export", os.path.join(package, folder), ref])
        p.check_returncode()
        if os.path.isfile(conandata_full_path):
            if os.path.isfile(conandata_path):
                os.remove(conandata_path)
            os.rename(conandata_full_path, conandata_path)
        p = subprocess.run(["conan", "search", ref, "--revisions", "--json", "revision.json"])
        p.check_returncode()
        with open("revision.json", "r") as stream:
            revisions = json.load(stream)
        if len(revisions) == 0:
            rev = ""
        elif len(revisions) == 1:
            rev = revisions[0]["revision"]
        else:
            print("unexpected revisions for %s: %s" % (ref, revisions))

        fullref = "%s#%s" % (ref, rev)


        p = subprocess.run(["conan", "search", fullref, "-r", "all", "-q", "os=FreeBSD", "--json", "binaries.json"])
        p.check_returncode()
        with open("binaries.json", "r") as stream:
            binaries = json.load(stream)
        assert not binaries["error"]
        binaries = binaries["results"]
        if len(binaries) > 0:
            binaries = binaries[0]
            binaries = binaries["items"]
            if len(binaries) > 0:
                binaries = binaries[0]
                binaries = binaries["packages"]
                if len(binaries) > 0:
                    continue
        print("no binaries for %s" % fullref)

        p = subprocess.run(["conan", "install", fullref, "-b", package])
        if p.returncode == 6:
            print("package %s not supported" % ref)
            continue
        elif p.returncode == 1:
            print("error while building %s, ignored" % ref)
            continue
        p.check_returncode()
        p = subprocess.run(["conan", "test", os.path.join(package, folder, "test_package", "conanfile.py"), fullref])
        if p.returncode == 1:
            print("Test of %s failed" % ref)
            continue
        p.check_returncode()
        p = subprocess.run(["conan", "upload", fullref, "--all"])
        p.check_returncode()
