# Charity Connect

## Project Description

Charity Connect is a web platform designed to connect generous donors with charitable institutions in need of various items and services. The platform aims to simplify the donation process and ensure that contributions reach organizations that can make the most impact.

## Features

*   **Institution Registration:** Charitable institutions can register and provide details about their organization and needed items.
*   **Institution Profiles:** Registered institutions have profiles displaying their information and current needs.
*   **Donor Donations:** Donors can browse institutions and donate various items (clothing, food, furniture, electronics, etc.) and services.
*   **Automated Notifications:** Institutions receive email notifications when a donor makes a donation.
*   **Dynamic Item Catalog:** The list of donation items can be updated as needed.
*   **Simple Navigation:** The website features a clean and easy-to-use navigation with Home, Institutions, and About pages.
*   **Admin Portal:** Admins can manage institutions, users, and view/export all donations.
*   **Email Confirmation:** Users must confirm their email address before logging in.
*   **Session Timeout:** Users are automatically logged out after 5 minutes of inactivity for security.
*   **Secure Passwords:** Passwords are hashed and strong password rules are enforced.
*   **CSRF Protection:** (Recommended) Use Flask-WTF for CSRF protection on all forms.
*   **Export Donations:** Admins can export all or filtered donations to CSV.

## Target Users

*   **Donors:** Individuals and institutions who wish to donate items or services to charitable causes.
*   **Charitable Institutions:** Organizations (Learning Institutions, Children's Homes, Safehubs, etc.) that need donations to support their work.
*   **Admins:** Manage users, institutions, and donations.

## Technologies Used

*   **Frontend:** HTML, CSS, JavaScript
*   **Backend:** Python (Flask)
*   **Database:** PostgreSQL
*   **Authentication:** Flask-Login
*   **Email:** Flask-Mail (Gmail SMTP)
*   **Password Hashing:** bcrypt
*   **Token Generation:** itsdangerous
*   **Environment Variables:** python-dotenv (recommended)

## Getting Started

1. **Clone the repository**
2. **Install dependencies:**
    ```
    pip install -r requirements.txt
    ```
3. **Set environment variables** for secrets, database, and email (see `.env.example` for reference).
4. **Run the app:**
    ```
    flask run
    ```
5. **Access the site** at `http://localhost:5000`

## Session Management

- Users are automatically logged out after 5 minutes of inactivity for security.

## Exporting Donations

- Admins can search and export donations to CSV from the admin portal.

## Security Notes

- All secrets (secret key, DB password, mail password) should be set as environment variables.
- Use HTTPS in production.
- Use strong, unique passwords for all admin accounts.

## Contributing

[Information on how others can contribute - to be added later]

## License

[License information - to be added later]

