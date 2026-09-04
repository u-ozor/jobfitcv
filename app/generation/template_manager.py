# app/template_manager

import os


TEMPLATE_ROOT = "templates"


def get_template_dir(template_name: str):
    return os.path.join(
        TEMPLATE_ROOT,
        template_name
    )


def get_template_path(
    template_name: str,
    filename: str
):
    return os.path.join(
        get_template_dir(template_name),
        filename
    )


def load_template(template_name: str):
    path = get_template_path(
        template_name,
        "resume.html"
    )

    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def load_css(template_name: str):
    path = get_template_path(
        template_name,
        "styles.css"
    )

    with open(path, "r", encoding="utf-8") as f:
        return f.read()