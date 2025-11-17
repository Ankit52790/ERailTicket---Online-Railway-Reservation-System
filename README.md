# ERailTicket – Railway Reservation System 🚆

ERailTicket is a **Streamlit-based Railway Reservation System** inspired by the **IRCTC** UI.  
It supports **user sign up & login with email verification, admin train management, and seat booking/cancellation** using SQLite.

---

## ✨ Features

### 👤 Authentication & Security
- User **sign up / login** with **hashed passwords (PBKDF2 + salt)**
- Email-based **account verification** using one-time verification codes
- **Forgot password** flow with reset codes
- Separate roles: **Admin** and **User**

### 🚆 Train & Seat Management
- Admin can:
  - **Add trains** with train number, name, source, destination, and departure date
  - **View all trains** in a table view
  - **Delete trains**, which also removes their seat tables
- Automatic seat table creation (`1–50` seats per train)
- Seats categorized as **Window / Aisle / Middle** based on seat number

### 🎫 Ticket Booking / Cancellation
- Users can:
  - Book tickets by selecting **Train Number**, **Seat Type**, and passenger details
  - System automatically picks the **next available seat** of that type
  - Cancel tickets by train number + seat number
- Detailed seat view showing:
  - Seat number, type, booked/unbooked, passenger name, age, gender

### 🔍 Search & View
- Search trains:
  - By **train number** or **From–To + date**
- View:
  - All trains
  - Seat layout for a specific train

### 🎨 IRCTC-style UI
- Built with **Streamlit**
- Custom CSS for:
  - Branded header with **ERailTicket logo**
  - Card-based layout
  - Primary IRCTC-like blue + orange theme
- Responsive layout with Streamlit tabs

---

## 🏗️ Tech Stack

- **Python 3**
- **Streamlit** – frontend + app framework
- **SQLite** – local database
- **Pandas** – tabular data display
- **Pillow (PIL)** – logo handling
- **smtplib + python-dotenv** – email verification using environment variables

---

## 📂 Project Structure

```text
ERailTicket/
├── app.py                  # Main Streamlit app
├── logo.png                # ERailTicket logo
├── README.md               # Project documentation  
├── .gitignore              # Git ignore rules
└── .streamlit/
    └── secrets.toml        # (optional) Streamlit Cloud / deployment secrets
