<p align="center">
  <a href="https://github.com/The-Commit-Company/commit">
  <img src="dashboard/src/assets/commit-logo.png" alt="Commit logo" height="100" />
     </a>

   <h3 align="center">commit</h3>
  <p align="center">Developer tooling for the Frappeverse 🪐
     <br />
    <br />
    <a href="https://frappecloud.com/marketplace/apps/commit"><strong>Install on Frappe Cloud »</strong></a>
    <br />
    <br />
    <a href="https://commit.frappe.cloud/"><strong>Learn More »</strong></a>
    <br />
    <br />
    <a href="https://github.com/The-Commit-Company/commit/issues">Issues</a>
    .
    <a href="https://github.com/sponsors/The-Commit-Company?frequency=one-time">Sponsor Us!</a>
  </p>
</p>
<p align="center">
  <a href="https://github.com/The-Commit-Company/commit/blob/main/LICENSE">
    <img alt="license" src="https://img.shields.io/badge/license-AGPLv3-blue">
  </a>
     <a href="https://github.com/The-Commit-Company/commit/stargazers"><img src="https://img.shields.io/github/stars/The-Commit-Company/commit" alt="Github Stars"></a>
     <a href="https://github.com/The-Commit-Company/commit/pulse"><img src="https://img.shields.io/github/commit-activity/m/The-Commit-Company/commit" alt="Commits-per-month"></a>
</p>


# [commit](https://commit.frappe.cloud/)

Born out of a need to improve developer tooling for Frappe, "Commit" allows you to visualize your app's database schema and view all its APIs, generate documentation for the APIs, and manage your documentation through Commit Docs - improving developer productivity and security of your critical applications.


## Basic Installation

The below guide assumes that you already have a working Frappe and Bench installation. If you do not have it, then please head over to [Official Installation Guide](https://frappeframework.com/docs/user/en/installation).

Go ahead and create a fresh new bench:
```bash
# Initialize a new bench
bench init commit
```

```bash
# Get the Commit app
bench get-app https://github.com/The-commit-company/commit
```

```bash
# Create a new site
bench new-site my-site.localhost
```

```bash
# Install the Commit app on the site
bench --site my-site.localhost install-app commit
```

## Tech Stack

### Common Across Web and Mobile
- **Frappe Framework**: An open-source full-stack development framework using Python, MariaDB/Postgres, socket.io, and Redis.
- **React**: A JavaScript library for building user interfaces.
- **Frappe React SDK**: A React Hooks library for handling auth, data fetching, and API calls to the Frappe Framework backend.
- **Tailwind CSS**: A utility-first CSS framework.
- **MDX**: A Markdown format that allows you to use JSX components in your Markdown files.
- **OpenAI API**: For AI-assisted documentation generation and editing.

---

## Production Setup

### Managed Hosting
You can try **Frappe Cloud**, a simple, user-friendly, and sophisticated open-source platform to host Frappe applications with peace of mind.

It takes care of installation, setup, upgrades, monitoring, maintenance, and support of your Frappe deployments. It is a fully featured developer platform with the ability to manage and control multiple Frappe deployments.

[Try on Frappe Cloud](https://frappecloud.com/)
<img width="1510" alt="Screenshot 2025-04-02 at 6 35 01 PM" src="https://github.com/user-attachments/assets/047758d4-53cc-4418-810f-8bb8921910c5" />


## Key Features

- **Database Schema Visualization**: View and analyze your application's database structure graphically.<img width="1510" alt="Screenshot 2025-04-02 at 6 34 50 PM" src="https://github.com/user-attachments/assets/b6eff25e-5661-43d7-b88c-3e1ce659c370" />

- **API Explorer**: Easily access and test API endpoints within the Frappe framework.<img width="1510" alt="image" src="https://github.com/user-attachments/assets/66dc42cb-b9fe-4831-9da3-65a88801a9b8" /><img width="1510" alt="image" src="https://github.com/user-attachments/assets/94b0a494-1266-44ef-92db-42ab779d85a2" />


- **Command Reference**: Get an overview of available Frappe commands.
- <img width="1510" alt="image" src="https://github.com/user-attachments/assets/bf95e91e-9ce2-4d84-bcdf-5a5e8b7326d9" />

- **Documentation Generation**: Auto-generate API documentation.<img width="1510" alt="image" src="https://github.com/user-attachments/assets/9e05e048-e2e5-43ab-bac6-014c1884d7da" />

- **OpenAI Integration**: Edit and refine documentation using AI assistance.
- **Commit Docs**: Manage and publish documentation for your applications.<img width="1510" alt="image" src="https://github.com/user-attachments/assets/38bcadab-0ce9-4895-bd4e-1a547be440fa" />

- **Docs Dashboard**: View and manage all your documentation in one place.
- <img width="1510" alt="image" src="https://github.com/user-attachments/assets/dff479e6-10e4-44e8-b1dc-838071456882" />

- **MDX Support**: Write JavaScript and React components in your Markdown files.
- <img width="1510" alt="image" src="https://github.com/user-attachments/assets/66797334-c07a-452c-9c27-7157f41c5f1a" />

- **Customizable**: Tailor the tool to fit your specific needs and preferences.
