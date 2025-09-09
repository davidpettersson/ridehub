# Architecture Guidelines

## Model and Business Logic Organization
- All models and business logic must be placed in the backoffice application
- Avoid using fat models. Instead, place logic in services
- Create services for domains of logic, such as users, registrations, events and so on
- Create methods in each service for key operations, such as fetching all events

## Development Approach
- Follow service-oriented architecture patterns
- Keep models lightweight and focused on data structure
- Centralize business logic in dedicated service classes