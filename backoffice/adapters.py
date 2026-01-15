from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class RideHubSocialAccountAdapter(DefaultSocialAccountAdapter):
    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        return user

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        user.email = data.get('email', '').lower()
        return user
