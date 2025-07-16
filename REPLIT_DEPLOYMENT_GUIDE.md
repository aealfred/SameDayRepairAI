# Replit Deployment Guide for Same-Day-Repair AI

This guide provides step-by-step instructions to deploy and run the Same-Day-Repair AI application on Replit, using a persistent cloud database to store user and session data.

## Overview

Because Replit has a temporary (ephemeral) filesystem, we cannot use the local SQLite database (`site.db`) for permanent storage. Instead, we will use a free, cloud-hosted PostgreSQL database from a service called **Neon**.

The process involves three main parts:
1.  **Setting up the Database on Neon.**
2.  **Configuring the Replit Project.**
3.  **Initializing the Database on Replit.**

---

## Part 1: Create a Free PostgreSQL Database on Neon

First, you'll need to create the database that your Replit app will connect to.

1.  **Sign Up for Neon:**
    *   Go to [neon.tech](https://neon.tech/) and sign up for a free account. You can use a Google, GitHub, or email account.

2.  **Create a New Project:**
    *   After signing up, you will be prompted to create a new project. Give it a name, like `samedayrepair-ai-db`.
    *   Choose the latest version of PostgreSQL.
    *   Select the free tier. A database will be created for you automatically within this project.

3.  **Get the Connection String:**
    *   Once your project is ready, you will see a dashboard.
    *   Find the **Connection Details** section.
    *   Make sure the role selected is `neondb`.
    *   Look for a connection string labeled **"psql"** or **"Postgres"**. It will look something like this:
        ```
        postgres://<user>:<password>@<host>.neon.tech/neondb?sslmode=require
        ```
    *   **Copy this entire URL.** This is your `DATABASE_URL`. You will need it for the next part.

---

## Part 2: Configure Your Replit Project

Now, you will set up your Replit project to connect to your new Neon database.

1.  **Import Your Project:**
    *   In Replit, import your project from its GitHub repository.

2.  **Use Replit Secrets:**
    *   Secrets are used to store sensitive information like database passwords without putting them directly in your code.
    *   In the left-hand menu of your Replit workspace, find the "Secrets" tab (it looks like a key icon 🔑).
    *   You need to add two secrets:

        *   **Secret 1: The Database URL**
            *   **Key:** `DATABASE_URL`
            *   **Value:** Paste the full `DATABASE_URL` you copied from Neon in Part 1.

        *   **Secret 2: The Flask Secret Key**
            *   **Key:** `FLASK_SECRET_KEY`
            *   **Value:** Generate a long, random string of characters. You can use a password generator for this. This key is used to secure user sessions.

    *   After adding them, your Secrets tab should look like this:

        ![Replit Secrets](https://i.imgur.com/example-secrets.png) <!-- Placeholder image -->

3.  **Check the `.replit` file:**
    *   Replit needs to know how to run your app. Open the `.replit` file in your workspace and ensure it contains the following `run` command:
        ```toml
        # .replit
        run = "flask run"
        ```
    *   You may also need an `onBoot` command to install dependencies:
        ```toml
        # .replit
        onBoot = "pip install -r requirements.txt"
        run = "flask run"
        ```

---

## Part 3: Initialize the Database on Replit

The final step is to create the `User` and `ChatSession` tables in your new cloud database. You only need to do this once.

1.  **Open the Shell:**
    *   In your Replit workspace, open the "Shell" tab.

2.  **Run the Database Migrations:**
    *   Type the following commands into the shell, one at a time, and press Enter after each one.

    *   First, set the Flask app environment variable:
        ```sh
        export FLASK_APP=app.py
        ```

    *   Next, initialize the migrations folder (you might see an error if it already exists, which is okay):
        ```sh
        flask db init
        ```

    *   Then, generate the migration script:
        ```sh
        flask db migrate -m "Initial migration for Replit"
        ```

    *   Finally, apply the migration to create the tables in your Neon database:
        ```sh
        flask db upgrade
        ```

---

## Deployment Complete!

Your application is now fully configured. Click the **"Run"** button at the top of your Replit workspace. The application will start, connect to your persistent Neon database, and be ready for users.

From now on, you only need to press "Run" to start the application. All user data will be safely stored in your cloud database. 