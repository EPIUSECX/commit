import requests

GITHUB_API_URL = "https://api.github.com"
REQUEST_TIMEOUT = (5, 30)


def prepare_headers(
    access_token=None, type="bearer", accept="application/vnd.github+json"
):
    headers = {
        "Accept": accept,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if access_token and access_token != "*":
        headers["Authorization"] = f"{type} {access_token}"
    return headers


def github_get(path: str, *, headers: dict, params: dict | None = None):
    response = requests.get(
        f"{GITHUB_API_URL}{path}",
        headers=headers,
        params=params,
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code == 404:
        return response
    response.raise_for_status()
    return response


def get_user(access_token=None):
    """
    Get user details from github
    """
    headers = prepare_headers(access_token)
    response = github_get("/user", headers=headers)
    return response.json()


def get_user_organizations(access_token=None):
    """
    Get user organizations from github
    """
    headers = prepare_headers(access_token)
    response = github_get("/user/orgs", headers=headers)
    return response.json()


def get_organization_repos(access_token, organization):
    """
    Get repositories in an organization from Github
    """
    headers = prepare_headers(access_token)
    response = github_get(f"/orgs/{organization}/repos", headers=headers)
    return response.json()


def get_file_in_repo(access_token: str, organization: str, repo: str, path: str):
    """
    Get file in a repository from Github
    """
    headers = prepare_headers(access_token, accept="application/vnd.github.raw")
    response = github_get(
        f"/repos/{organization}/{repo}/contents/{path}", headers=headers
    )
    return response.text


def get_all_files_in_repo(
    access_token: str, organization: str, repo: str, path: str = ""
):
    """
    Get all files in a repository from Github
    """

    # TODO: For every file, we need to store it in the database with the commit hash so that we do not need to call this API again to fetch the same result
    headers = prepare_headers(access_token)
    response = github_get(
        f"/repos/{organization}/{repo}/contents/{path}", headers=headers
    )
    return response.json()


def search_for_file_in_repo(
    access_token: str,
    organization: str,
    repo: str,
    query: str | None = None,
    extension: str | None = None,
    page: int = 1,
    per_page: int = 100,
    accept=None,
):
    """
    Search for a file in a repository from Github
    query examples:
    1. "CRM in:file" - searches for keyword CRM in all files
    2. "path:erpnext/crm.doctype" - searches for all files in path erpnext/crm.doctype
    3. Combined query: "path:erpnext/crm.doctype+CRM in:file" - searches for keyword CRM in all files in path erpnext/crm.doctype

    Extension and repo will be added to search query automatically
    """

    # TODO: This API is expensive to use. We need to store the result based on commit hash and return from our own database
    headers = prepare_headers(access_token, accept=accept)
    qualifiers = [query] if query else []
    if extension:
        qualifiers.append(f"extension:{extension}")
    qualifiers.append(f"repo:{organization}/{repo}")
    response = github_get(
        "/search/code",
        headers=headers,
        params={"q": " ".join(qualifiers), "page": page, "per_page": per_page},
    )
    return response.json()
