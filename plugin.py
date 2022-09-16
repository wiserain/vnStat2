from pathlib import Path

# third-party
from flask import Blueprint

# pylint: disable=import-error
from framework import app, path_data
from framework.logger import get_logger
from framework.util import Util
from framework.common.plugin import get_model_setting, Logic, default_route_single_module


class PlugIn:
    package_name = __name__.split(".", maxsplit=1)[0]
    logger = get_logger(package_name)
    ModelSetting = get_model_setting(package_name, logger, table_name=f"plugin_{package_name}_setting")

    blueprint = Blueprint(
        package_name,
        package_name,
        url_prefix=f"/{package_name}",
        template_folder=Path(__file__).parent.joinpath("templates"),
    )

    plugin_info = {
        "category_name": "tool",
        "version": "1.2.3",
        "name": "vnStat2",
        "home": "https://github.com/wiserain/vnStat2",
        "more": "https://github.com/wiserain/vnStat2",
        "supported_vnstat_version": ["2.6", "2.9"],
        "description": "vnStat 정보를 보여주는 플러그인",
        "developer": "wiserain",
        "zip": "https://github.com/wiserain/vnStat2/archive/master.zip",
        "icon": "",
    }

    menu = {
        "main": [package_name, "vnStat2"],
        "sub": [["setting", "설정"], ["traffic", "트래픽"], ["log", "로그"]],
        "category": "tool",
    }
    home_module = "traffic"

    module_list = None
    logic = None

    def __init__(self):
        db_file = Path(path_data).joinpath("db", f"{self.package_name}.db")
        app.config["SQLALCHEMY_BINDS"][self.package_name] = f"sqlite:///{db_file}"

        Util.save_from_dict_to_json(self.plugin_info, Path(__file__).parent.joinpath("info.json"))


plugin = PlugIn()

from .logic import LogicMain

plugin.module_list = [LogicMain(plugin)]

# (logger, package_name, module_list, ModelSetting) required for Logic
plugin.logic = Logic(plugin)
# (;ogger, package_name, module_list, ModelSetting, blueprint, logic) required for default_route
default_route_single_module(plugin)
