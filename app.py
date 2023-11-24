import json
import sys

from flask import Flask, render_template

app = Flask("python_rebuild_status")


def load_data(filename):
    with open(filename, "r", encoding="utf=8") as f:
        return {row.strip() for row in f.readlines()}


def load_json(filename):
    with open(filename, "r", encoding="utf=8") as f:
        return json.load(f)


def load_monitor_report(filename):
    monitor = {}
    with open(filename, "r", encoding="utf=8") as f:
        for line in f:
            pkgname, state = line.strip().split("\t")
            monitor[pkgname] = state
    return monitor


ALL_TO_BUILD = sorted(load_data("data/python312.pkgs"))
HISTORICALLY_SUCCESSFUL = load_data("data/python313.pkgs")
FAILED = load_data("data/failed.pkgs")
WAITING = load_data("data/waiting.pkgs")
ALL_IN_COPR = load_monitor_report("data/copr.pkgs")
BUGZILLAS = load_json("data/bzurls.json")


def count_pkgs_with_state(build_status, looked_for):
    return sum(1 for state in build_status.values() if state == looked_for)


def assign_build_status():
    build_status = {}
    for pkg in ALL_TO_BUILD:
        # python3.12 has been rebuilt but it doesn't require 'python(abi) = 3.13'
        if pkg == "python3.12":
            status = "🟢"
        # pkg can build once and never again, so let's look at the last
        # build to determine if we need to take a look at it anyways
        elif pkg in HISTORICALLY_SUCCESSFUL:
            last_build_state = ALL_IN_COPR[pkg]
            if last_build_state == "failed":
                status = "🟠"
            elif last_build_state == "succeeded":
                status = "🟢"
            else:
                # package is waiting in build queue, we don't know its status yet
                status = "⚪"
        elif pkg in FAILED:
            status = "🔴"
        elif pkg in WAITING:
            status = "⚪"
        build_status[pkg] = status
    return build_status


def find_maintainers():
    # bits borrowed from: https://pagure.io/fedora-misc-package-utilities/blob/master/f/find-package-maintainers
    maintainers = load_json('data/pagure_owner_alias.json')
    return {pkg: maintainers["rpms"][pkg] for pkg in ALL_TO_BUILD}


def sort_by_maintainers(packages_with_maintainers, build_status):
    # get maintainer, their pkgs and build statuses
    by_maintainers = {}
    for pkg, maints in packages_with_maintainers.items():
        for maint in maints:
            by_maintainers.setdefault(maint, []).append(f"{pkg} {build_status[pkg]}")
    return sorted(by_maintainers.items())


build_status = assign_build_status()
packages_with_maintainers = find_maintainers()
status_by_packages = [(pkg, build_status[pkg], packages_with_maintainers[pkg]) for pkg in ALL_TO_BUILD]
status_by_maintainers = sort_by_maintainers(packages_with_maintainers, build_status)


@app.route('/')
def index():
    return render_template(
        'index.html',
        number_pkgs_to_rebuild=len(ALL_TO_BUILD),
        number_pkgs_success=count_pkgs_with_state(build_status, "🟢"),
        number_pkgs_flaky=count_pkgs_with_state(build_status, "🟠"),
        number_pkgs_failed=len(FAILED),
        number_pkgs_waiting=len(WAITING),
    )

@app.route('/packages/')
def packages():
    return render_template(
        'packages.html',
        status_by_packages=status_by_packages,
    )

@app.route('/maintainers/')
def maintainers():
    return render_template(
        'maintainers.html',
        status_by_maintainers=status_by_maintainers,
    )

@app.route('/failures/')
def failures():
        return render_template(
        'failures.html',
        status_failed=BUGZILLAS,
    )
