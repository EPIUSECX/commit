import importlib

import frappe


@frappe.whitelist()
def get_project_app_commands(app: str, app_path: str = None) -> dict:
    """
    Gets the commands for the app
    """
    if app_path:
        frappe.throw(
            "Commands from cloned repositories cannot be executed. Static command analysis is not yet available.",
            frappe.PermissionError,
        )
    if not is_system_manager():
        frappe.throw("System Manager role required", frappe.PermissionError)
    return get_site_app_commands(app)


@frappe.whitelist()
def get_site_app_commands(app: str) -> dict:
    if not is_system_manager():
        frappe.throw("System Manager role required", frappe.PermissionError)
    try:
        app_command_module = importlib.import_module(f"{app}.commands")
    # Call get_commands if it is a callable
    except ModuleNotFoundError as e:
        if e.name == f"{app}.commands":
            return []
        frappe.log_error(frappe.get_traceback(), "Unable to load app commands")
        return []

    command_list = []
    if hasattr(app_command_module, "commands"):
        commands_from_function = app_command_module.commands
        if commands_from_function:
            for command_instance in commands_from_function:
                help_text = getattr(command_instance, "help", "No help text available")
                name = getattr(command_instance, "name", [])
                obj = {"name": name, "help": help_text}
                command_list.append(obj)
    return command_list


def is_system_manager():
    user = frappe.session.user
    roles = frappe.get_roles(user)
    return "System Manager" in roles
