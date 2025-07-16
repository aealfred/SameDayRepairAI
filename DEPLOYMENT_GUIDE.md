# Deploying Your Python + JavaScript App

This guide explains how to deploy your application, which consists of a Python Flask backend and a JavaScript-powered frontend.

## The Challenge: GitHub Pages is for Static Sites Only

GitHub Pages is a fantastic service for hosting websites directly from a GitHub repository. However, it can only serve **static files**. These are files like HTML, CSS, JavaScript, and images that are sent directly to the user's browser without any server-side processing.

Your project has a Python backend (`app.py`, `API_Interface.py`). This backend code needs to run on a server to handle API requests, manage chat sessions, and securely communicate with the Google Gemini API. GitHub Pages **cannot** run Python code.

Therefore, you cannot simply upload the entire project to a repository and have it work on GitHub Pages.

## Solution: Hybrid Hosting (Recommended)

The best approach is to host your backend and frontend in different places that are suited for their technologies.

### Step 1: Deploy the Python Backend

You need to host your Flask application on a platform that supports Python web apps. Here are some popular options with free or low-cost tiers:

*   **Heroku:** A popular platform-as-a-service that makes deploying Python apps relatively simple.
*   **PythonAnywhere:** Specifically designed for hosting Python applications. It has a beginner-friendly free tier.
*   **Google Cloud Run:** A serverless platform where you can run your app in a container.
*   **AWS Elastic Beanstalk / Lambda:** Powerful options from Amazon Web Services.

Once you deploy your backend to one of these services, it will have a public URL, for example: `https://your-app-name.herokuapp.com`.

### Step 2: Deploy the Frontend to GitHub Pages

You can host your `templates/API Interface.html`, `static/styles.css`, and any other static assets on GitHub Pages.

1.  Create a new repository on GitHub (or use your existing one).
2.  Push your frontend files (`templates/API Interface.html` and the `static` directory) to the repository.
3.  In your repository's settings, go to the "Pages" section and configure it to build from your main branch.

### Step 3: Connect the Frontend to the Backend

After deploying both parts, you need to tell your frontend (running on GitHub Pages) where to find your backend (running on Heroku, etc.).

In your `templates/API Interface.html` file, you need to change the `fetch` URLs from relative paths to the full URL of your deployed backend.

**Change this:**
```javascript
// ... existing code ...
        try {
            const response = await fetch('/api/new_chat', { // <--- RELATIVE PATH
                method: 'POST',
// ... existing code ...
```

**To this (example using Heroku):**
```javascript
// ... existing code ...
        try {
            const response = await fetch('https://your-app-name.herokuapp.com/api/new_chat', { // <--- ABSOLUTE URL
                method: 'POST',
// ... existing code ...
```

You will need to do this for all `fetch` calls in your JavaScript (e.g., for `/api/new_chat` and `/api/chat_message`).

---

## Alternative (Not Recommended): Client-Side Only

It is technically possible to rewrite the application to run entirely in the browser without a Python backend. This would involve making calls to the Google Gemini API directly from your JavaScript code.

**However, this approach has a critical security flaw:**

> **WARNING:** To call the Gemini API from JavaScript, you would have to embed your `GOOGLE_API_KEY` directly in your public-facing code. A malicious user could easily find this key, steal it, and use it for their own purposes, potentially costing you a lot of money.

If you were to take this path, you would need to use a special, highly restricted API key and monitor your usage very carefully. A better way to secure the key on the client-side is to use a proxy server or a serverless function, but that adds complexity and is similar to the hybrid hosting model.

For these reasons, the **Hybrid Hosting** model is the standard and most secure way to build and deploy an application like this. 