from django import forms
from django.contrib.admin.widgets import AdminSplitDateTime
from django.utils.safestring import mark_safe

class EndsAtWidget(AdminSplitDateTime):
    def render(self, name, value, attrs=None, renderer=None):
        widget_html = super().render(name, value, attrs, renderer)
        
        links_html = f'''
        <p style="margin-left: 2em; line-height: 20px; margin-top: 6px; padding-top: 4px;">
            Quick set: 
            <a href="#" onclick="setEndsAtDuration(1, 'id_starts_at', 'id_{name}'); return false;">1 hour</a>, 
            <a href="#" onclick="setEndsAtDuration(2, 'id_starts_at', 'id_{name}'); return false;">2 hours</a>, or 
            <a href="#" onclick="setEndsAtDuration(5, 'id_starts_at', 'id_{name}'); return false;">5 hours</a> after start time.
        </p>
        '''
        
        return mark_safe(widget_html + links_html)
    
    @property
    def media(self):
        base_media = super().media
        custom_js = forms.Media(js=(
            'backoffice/js/ends_at_widget.js',
        ))
        return base_media + custom_js 