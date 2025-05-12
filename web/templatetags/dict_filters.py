from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary by key"""
    if not dictionary:
        return None
        
    # Try with the original key
    if key in dictionary:
        return dictionary[key]
        
    # Try with string conversion
    str_key = str(key)
    if str_key in dictionary:
        return dictionary[str_key]
        
    return None 