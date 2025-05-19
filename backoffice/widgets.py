from django import forms
from django.contrib.admin.widgets import AdminSplitDateTime
from django.utils.safestring import mark_safe

class EndsAtWidget(AdminSplitDateTime):
    def render(self, name, value, attrs=None, renderer=None):
        widget_html = super().render(name, value, attrs, renderer)
        
        # Create a unique ID for the select dropdown
        dropdown_id = f'ends_at_dropdown_{name}'
        
        dropdown_html = f'''
        <div style="margin-left: 2em; margin-top: 6px; padding-top: 4px;">
            <select id="{dropdown_id}" style="min-width: 220px; padding: 4px;" 
                    onchange="if(this.value) {{ 
                        setEndsAtTime(parseInt(this.value), 'id_starts_at', 'id_{name}'); 
                        this.selectedIndex = 0; 
                    }}">
                <option value="">Quick set...</option>
                <option value="1">Add 1 hour</option>
                <option value="2">Add 2 hours</option>
                <option value="3">Add 3 hours</option>
                <option value="5">Add 5 hours</option>
                <option value="8">Add 8 hours</option>
            </select>
        </div>
        '''
        
        return mark_safe(widget_html + dropdown_html)
    
    @property
    def media(self):
        base_media = super().media
        custom_js = forms.Media(js=(
            'backoffice/js/time_calculator.js',
        ))
        return base_media + custom_js


class RegistrationClosesAtWidget(AdminSplitDateTime):
    def render(self, name, value, attrs=None, renderer=None):
        widget_html = super().render(name, value, attrs, renderer)
        
        # Create a unique ID for the select dropdown
        dropdown_id = f'registration_closes_dropdown_{name}'
        
        dropdown_html = f'''
        <div style="margin-left: 2em; margin-top: 6px; padding-top: 4px;">
            <select id="{dropdown_id}" style="min-width: 220px; padding: 4px;" 
                    onchange="if(this.value) {{ 
                        var option = this.value.split(':')[0];
                        var value = this.value.split(':')[1];
                        setRegistrationClosesTime(option, value, 'id_starts_at', 'id_{name}'); 
                        this.selectedIndex = 0; 
                    }}">
                <option value="">Quick set...</option>
                <option value="hours_before:2">2 hours before start</option>
                <option value="hours_before:3">3 hours before start</option>
                <option value="day_of:12:00">Same day at noon</option>
                <option value="day_before:12:00">Day before at noon</option>
                <option value="day_before:16:00">Day before at 4 pm</option>
                <option value="day_before:17:00">Day before at 5 pm</option>
                <option value="day_before:20:00">Day before at 8 pm</option>
                <option value="day_before:21:00">Day before at 9 pm</option>
            </select>
        </div>
        '''
        
        return mark_safe(widget_html + dropdown_html)
    
    @property
    def media(self):
        base_media = super().media
        custom_js = forms.Media(js=(
            'backoffice/js/time_calculator.js',
        ))
        return base_media + custom_js 