# RideHub Design Standards

This document outlines the design standards for RideHub templates to maintain a consistent look and feel across the application.

## Template Structure

All templates should:

1. Extend the base template: `{% extends 'web/_base.html' %}`
2. Define a title block: `{% block title %}Page Title{% endblock %}`
3. Place content within the content block: `{% block content %}...{% endblock %}`

## Components

### Cards

Use the `.card` class for content containers:

```html
<div class="card rounded-lg">
    <div class="p-6">
        <!-- Card content here -->
    </div>
</div>
```

### Buttons

Use the `.btn-primary` class for primary actions:

```html
<button type="submit" class="btn-primary">Button Text</button>
```

For full-width buttons:

```html
<button type="submit" class="btn-primary w-full">Button Text</button>
```

### Forms

1. Load form filters: `{% load form_filters %}`
2. Use the following structure for form fields:

```html
<div class="mb-4">
    <label class="form-label">{{ field.label }}</label>
    {{ field|addclass:"form-input" }}
</div>
```

For select fields:

```html
<label class="form-label">{{ field.label }}</label>
<select name="field_name" class="form-select">
    <!-- Options here -->
</select>
```

### Alerts/Notifications

Success messages:

```html
<div class="p-4 bg-green-50 dark:bg-green-900 text-green-700 dark:text-green-200 rounded-md">
    <p class="flex items-center">
        <i class="bi bi-check-circle mr-2 text-lg"></i>
        Success message here
    </p>
</div>
```

Info messages:

```html
<div class="p-4 bg-blue-50 dark:bg-blue-900 text-blue-700 dark:text-blue-200 rounded-md">
    <p class="flex items-center">
        <i class="bi bi-info-circle mr-2 text-lg"></i>
        Info message here
    </p>
</div>
```

### Typography

- Page headings: `<h1 class="text-2xl font-bold text-gray-900 dark:text-white mb-6">Heading</h1>`
- Section headings: `<h2 class="text-xl font-semibold text-gray-800 dark:text-gray-200 mb-3">Heading</h2>`
- Item headings: `<h3 class="text-lg font-medium text-gray-900 dark:text-white mb-1">Heading</h3>`

### Badges

```html
<span class="badge badge-primary">Badge Text</span>
<span class="badge badge-warning">Warning</span>
<span class="badge badge-danger">Error</span>
```

## Layout Patterns

### Centered Content Card

For login screens and similar content:

```html
<div class="max-w-md mx-auto">
    <div class="card rounded-lg">
        <div class="p-6">
            <!-- Content here -->
        </div>
    </div>
</div>
```

### List Views

For displaying lists of items:

```html
<div class="space-y-6">
    <h1 class="text-3xl font-bold text-gray-900 dark:text-white">List Title</h1>
    
    <div class="space-y-3">
        {% for item in items %}
        <a href="{% url 'item_detail' item.id %}" class="block hover:no-underline">
            <div class="card hover:shadow-lg transition-shadow duration-300">
                <div class="p-4">
                    <!-- Item content -->
                </div>
            </div>
        </a>
        {% empty %}
        <div class="py-12 text-center">
            <p class="text-gray-500 dark:text-gray-400">No items found.</p>
        </div>
        {% endfor %}
    </div>
</div>
```

## Icons

The application uses Bootstrap Icons. Include them with:

```html
<i class="bi bi-icon-name"></i>
```

Common icons:
- Clock: `bi-clock`
- Location: `bi-geo-alt`
- Check: `bi-check-circle`
- Info: `bi-info-circle`
- Warning: `bi-exclamation-triangle`
- Email: `bi-envelope` 