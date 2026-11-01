"""Offline corpus tools and narrow deterministic citation checks, not an LLM judge."""
import json
from pathlib import Path

from skills.skills import SkillError


class ResearchCorpus:
    """Only search/read the explicitly supplied public source mapping."""
    def __init__(self, sources):
        if not isinstance(sources, dict) or not sources or len(sources) > 32:
            raise ValueError('Supply 1–32 sources')
        if any(not isinstance(k, str) or not isinstance(v, str) or len(v) > 12000
               for k, v in sources.items()):
            raise ValueError('Invalid corpus')
        self.sources = dict(sources)

    @property
    def declarations(self):
        return [dict(name=name, description=description,
                     parameters_json_schema={'type': 'object', 'properties': {argument: {'type': 'string'}},
                                             'required': [argument], 'additionalProperties': False})
                for name, description, argument in (
                    ('corpus_search', 'Search the fixed public corpus; does not access the web.', 'query'),
                    ('corpus_read', 'Read one exact source identifier from the fixed corpus.', 'source'))]

    async def execute(self, name, arguments):
        if not isinstance(arguments, dict):
            raise SkillError('Invalid corpus arguments')
        if name == 'corpus_search' and set(arguments) == {'query'} and isinstance(arguments['query'], str):
            query = arguments['query'].casefold()
            return {'sources': [key for key, text in self.sources.items() if query in text.casefold()]}
        if name == 'corpus_read' and set(arguments) == {'source'} and isinstance(arguments['source'], str):
            source = arguments['source']
            if source not in self.sources:
                raise SkillError('Source unavailable in the fixed corpus')
            return {'source': source, 'text': self.sources[source]}
        raise SkillError('Tool or arguments denied by research corpus policy')


def assess(claims, corpus, *, required_claims=(), unavailable=False, gap=None):
    """Check exact quoted evidence and required answers; not semantic entailment."""
    errors = []
    if not isinstance(claims, list) or len(claims) > 32:
        raise ValueError('Claims must be a bounded list')
    if unavailable:
        valid = not claims and isinstance(gap, str) and bool(gap.strip())
        return {'passed': valid, 'errors': [] if valid else ['Expected an explicit evidence gap']}
    if not claims:
        errors.append('No supported claims supplied')
    texts = []
    for item in claims:
        if not isinstance(item, dict) or set(item) != {'claim', 'source', 'quote'}:
            errors.append('Invalid claim structure')
            continue
        claim, source, quote = item['claim'], item['source'], item['quote']
        if not all(isinstance(value, str) and value.strip() for value in (claim, source, quote)):
            errors.append('Claim, source, and quote are required')
            continue
        texts.append(claim)
        if required_claims and claim not in required_claims:
            errors.append('Claim is outside the declared fixture answers')
        if source not in corpus.sources or quote not in corpus.sources[source]:
            errors.append('Citation does not match a corpus passage')
    for required in required_claims:
        if required not in texts:
            errors.append('Required answer missing: ' + required)
    return {'passed': not errors, 'errors': errors,
            'limitation': 'Checks exact quotes and declared answers, not general semantic correctness'}


def seed_bundle():
    return json.loads((Path(__file__).parent / 'profiles/research.json').read_text())


async def fixture_trial(root):
    """Exercise native config/dispatch/capture with scripted provider messages only."""
    from google.genai import types
    from core.harness_config import live_config
    from .bundles import BundleRegistry
    from .evidence import EpisodeCapture, EpisodeStore
    from .research_runtime import execute_corpus_call

    registry = BundleRegistry(root)
    bundle = registry.register(seed_bundle())
    # A fixture trial never changes the user's active bundle.
    corpus = ResearchCorpus({'release-note': 'The public release supports offline corpus search.'})
    capture = EpisodeCapture(EpisodeStore(root), bundle, 'offline-scripted')
    configuration = live_config('Aoede', skills=corpus, bundle=bundle)
    capture.configure(configuration, 'offline-scripted')
    try:
        capture.input('What does the release support?')
        episode = capture.current
        await execute_corpus_call(corpus, types.FunctionCall(
            id='fixture-read', name='corpus_read', args={'source': 'release-note'}),
            capture=capture)
        answer = 'The release supports offline corpus search.'
        capture.output(answer)
        capture.finish('delivered_unverified')
        await capture.flush()
        assessment = assess([{'claim': answer, 'source': 'release-note',
                              'quote': corpus.sources['release-note']}], corpus, required_claims=[answer])
        return {'episode': episode, 'bundle': bundle.digest, 'assessment': assessment,
                'tool_responses': 1, 'provider': 'offline-scripted',
                'limitation': 'Tests shared prompt/dispatch/capture with scripted responses; '
                              'no Live voice events, model, or Harness² run'}
    finally:
        await capture.close()
