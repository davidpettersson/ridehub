from dataclasses import dataclass

from agents.models import AgentRequest


@dataclass(frozen=True)
class AgentMatch:
    family: str
    kind: str


AGENT_SIGNATURES = [
    ('claude-user', 'anthropic', AgentRequest.Kind.ASSISTANT),
    ('claude-searchbot', 'anthropic', AgentRequest.Kind.CRAWLER),
    ('claudebot', 'anthropic', AgentRequest.Kind.CRAWLER),
    ('anthropic-ai', 'anthropic', AgentRequest.Kind.CRAWLER),
    ('chatgpt-user', 'openai', AgentRequest.Kind.ASSISTANT),
    ('oai-searchbot', 'openai', AgentRequest.Kind.CRAWLER),
    ('gptbot', 'openai', AgentRequest.Kind.CRAWLER),
    ('perplexity-user', 'perplexity', AgentRequest.Kind.ASSISTANT),
    ('perplexitybot', 'perplexity', AgentRequest.Kind.CRAWLER),
    ('mistralai-user', 'mistral', AgentRequest.Kind.ASSISTANT),
    ('duckassistbot', 'duckduckgo', AgentRequest.Kind.ASSISTANT),
    ('google-extended', 'google', AgentRequest.Kind.CRAWLER),
    ('googleother', 'google', AgentRequest.Kind.CRAWLER),
    ('bytespider', 'bytedance', AgentRequest.Kind.CRAWLER),
    ('ccbot', 'commoncrawl', AgentRequest.Kind.CRAWLER),
    ('meta-externalagent', 'meta', AgentRequest.Kind.CRAWLER),
    ('applebot-extended', 'apple', AgentRequest.Kind.CRAWLER),
    ('amazonbot', 'amazon', AgentRequest.Kind.CRAWLER),
    ('cohere-ai', 'cohere', AgentRequest.Kind.CRAWLER),
]

SCRIPT_SIGNATURES = [
    'python-requests',
    'python-httpx',
    'python-urllib',
    'aiohttp',
    'node-fetch',
    'undici',
    'axios',
    'go-http-client',
    'curl/',
    'wget/',
    'okhttp',
    'libwww-perl',
    'guzzlehttp',
    'java/',
]

PROBE_PATHS = frozenset([
    '/llms.txt',
    '/llms-full.txt',
    '/.well-known/ai-plugin.json',
    '/.well-known/mcp.json',
])


class AgentDetectionService:
    def detect(self, user_agent: str | None) -> AgentMatch | None:
        if not user_agent:
            return None
        lowered = user_agent.lower()
        for needle, family, kind in AGENT_SIGNATURES:
            if needle in lowered:
                return AgentMatch(family=family, kind=kind)
        for needle in SCRIPT_SIGNATURES:
            if needle in lowered:
                return AgentMatch(family='generic', kind=AgentRequest.Kind.SCRIPT)
        return None

    def is_probe_path(self, path: str) -> bool:
        return path in PROBE_PATHS
