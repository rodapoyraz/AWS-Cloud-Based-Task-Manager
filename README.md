AWS Cloud Based Task Manager

A full-stack cloud-powered task management web application designed to help teams organize projects, assign responsibilities, manage deadlines, and collaborate efficiently in one centralized platform.

This project demonstrates practical skills in backend development, cloud deployment, authentication systems, database integration, and modern web application architecture.

Project Overview

Managing tasks across teams can become inefficient when communication, file sharing, and progress tracking are scattered across multiple tools.

The AWS Cloud Based Task Manager solves this problem by providing a centralized workspace where users can:

Create and manage tasks
Assign responsibilities
Set deadlines and priorities
Upload and manage files
Track progress in real time
Collaborate within teams
Access the system through the cloud

This project was built as a practical portfolio project to demonstrate real-world software development skills.

Key Features
User Authentication
Secure user registration
Login/logout system
Session management
Protected routes
Task Management
Create new tasks
Edit existing tasks
Delete tasks
Set task priority levels
Assign deadlines
Mark progress / status
Team Collaboration
Shared workspace for multiple users
Task visibility across teams
Better accountability and coordination
File Upload System
Upload project files
Store files securely in the cloud
Access resources from anywhere
Dashboard & Productivity
Organized task view
Status monitoring
Better workflow management
Tech Stack
Backend
Python
Flask
Frontend
HTML5
CSS3
JavaScript
Jinja2 Templates
Database / Storage
Cloud database integration
File storage services
Cloud / DevOps
AWS Cloud Services
GitHub Version Control
Project Structure
AWS-Cloud-Based-Task-Manager/
│── app/
│── templates/
│── static/
│── routes.py
│── config.py
│── requirements.txt
│── run.py
│── README.md
How It Works
Users create an account or log in.
After authentication, users access the dashboard.
Tasks can be created with title, description, deadline, and priority.
Files can be uploaded and attached to workflows.
Team members monitor progress and update statuses.
Data is stored securely through cloud services.
Installation Guide
Clone Repository
git clone https://github.com/rodapoyraz/AWS-Cloud-Based-Task-Manager.git
cd AWS-Cloud-Based-Task-Manager
Create Virtual Environment
python -m venv venv
Activate Environment
Windows
venv\Scripts\activate
Mac / Linux
source venv/bin/activate
Install Dependencies
pip install -r requirements.txt
Run Application
python run.py
Future Improvements
Email notifications
Task comments system
Kanban board interface
Real-time chat
Role-based permissions
Analytics dashboard
Mobile responsive redesign
API version for mobile apps
