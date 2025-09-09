# RideHub Project Guidelines

This directory contains project-specific guidelines and conventions for the RideHub application.

## Architecture & Code Organization
- [Architecture Guidelines](architecture.md) - Service-oriented architecture and business logic organization
- [Data Validation](data-validation.md) - Model validation requirements and data integrity

## Development Standards
- [Code Style](code-style.md) - Commenting, documentation, and UI design patterns
- [Testing Guidelines](testing.md) - Test structure and organization patterns

## Frontend & User Experience  
- [Frontend & Styling](frontend-styling.md) - CSS framework migration and mobile-first design principles

## Environment & Templates
- [Development Environment](development-environment.md) - Windows-focused development setup
- [Email Templates](email-templates.md) - Email template maintenance and testing

## Key Project Conventions
- Business logic resides in the `backoffice` application
- Use service classes instead of fat models
- No comments or docstrings in code
- Mobile-first responsive design
- Arrange-act-assert testing pattern
- Bootstrap CSS with global styling.css file