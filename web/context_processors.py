import os
from datetime import datetime
from django.utils import timezone


def version_info(request):
    """
    Context processor to provide git commit hash and Heroku release information
    to all templates.
    """
    context = {}
    
    # Get Heroku release version
    heroku_release = os.environ.get('HEROKU_RELEASE_VERSION', 'dev')
    context['heroku_release'] = heroku_release
    
    # Get git commit hash
    git_commit = os.environ.get('HEROKU_SLUG_COMMIT', '')
    if git_commit:
        # Truncate to first 7 characters for display
        context['git_commit_short'] = git_commit[:7]
        context['git_commit_full'] = git_commit
    else:
        # Fallback for development - try to get from git directly
        try:
            import subprocess
            result = subprocess.run(['git', 'rev-parse', 'HEAD'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                full_commit = result.stdout.strip()
                context['git_commit_short'] = full_commit[:7]
                context['git_commit_full'] = full_commit
            else:
                context['git_commit_short'] = 'unknown'
                context['git_commit_full'] = 'unknown'
        except Exception:
            context['git_commit_short'] = 'unknown'
            context['git_commit_full'] = 'unknown'
    
    # Get release timestamp
    release_created_at = os.environ.get('HEROKU_RELEASE_CREATED_AT', '')
    if release_created_at:
        try:
            # Parse ISO format timestamp
            release_time = datetime.fromisoformat(release_created_at.replace('Z', '+00:00'))
            context['release_created_at'] = release_time
        except Exception:
            context['release_created_at'] = None
    else:
        context['release_created_at'] = None
    
    # Create a formatted version string
    version_parts = []
    if heroku_release != 'dev':
        version_parts.append(heroku_release)
    if context.get('git_commit_short'):
        version_parts.append(context['git_commit_short'])
    
    context['version_string'] = ' • '.join(version_parts) if version_parts else 'Development'
    
    return context 