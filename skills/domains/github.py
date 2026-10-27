"""Github adapters extracted from the registry facade."""
from connectors import github


ADAPTERS = {
    'github.authorize': '_adapter_github_authorize',
    'github.status': '_adapter_github_connection_status',
    'github.repositories': '_adapter_github_list_repositories',
    'github.repository': '_adapter_github_get_repository',
    'github.files': '_adapter_github_list_repository_files',
    'github.file': '_adapter_github_read_repository_file',
    'github.find_relevant_files': '_adapter_github_find_relevant_files',
    'github.read_repository_files': '_adapter_github_read_repository_files',
    'github.analyze_repository': '_adapter_github_analyze_repository',
    'github.issues': '_adapter_github_list_issues',
    'github.issue': '_adapter_github_get_issue',
    'github.pulls': '_adapter_github_list_pull_requests',
    'github.pull': '_adapter_github_get_pull_request',
}

ADAPTER_COMMANDS = {
    'github.authorize': (),
    'github.status': (),
    'github.repositories': (),
    'github.repository': (),
    'github.files': (),
    'github.file': (),
    'github.issues': (),
    'github.issue': (),
    'github.pulls': (),
    'github.pull': (),
}


class GithubDomain:
    async def _adapter_github_connection_status(self):
        return await github.dispatch('github_connection_status', {})

    async def _adapter_github_authorize(self):
        return await github.dispatch('github_authorize', {})

    async def _adapter_github_list_repositories(self, max_results=20):
        return await github.dispatch('github_list_repositories', {'max_results': max_results})

    async def _adapter_github_get_repository(self, owner, repository):
        return await github.dispatch('github_get_repository', {'owner': owner, 'repository': repository})

    async def _adapter_github_list_repository_files(self, owner, repository, path=''):
        return await github.dispatch('github_list_repository_files', {
            'owner': owner, 'repository': repository, 'path': path})

    async def _adapter_github_read_repository_file(self, owner, repository, path):
        return await github.dispatch('github_read_repository_file', {
            'owner': owner, 'repository': repository, 'path': path})

    async def _adapter_github_find_relevant_files(self, owner, repository, query='', max_results=20):
        return await github.dispatch('github_find_relevant_files', {
            'owner': owner, 'repository': repository, 'query': query,
            'max_results': max_results})

    async def _adapter_github_read_repository_files(self, owner, repository, ref, paths):
        return await github.dispatch('github_read_repository_files', {
            'owner': owner, 'repository': repository, 'ref': ref, 'paths': paths})

    async def _adapter_github_analyze_repository(self, owner, repository, query=''):
        return await github.dispatch('github_analyze_repository', {
            'owner': owner, 'repository': repository, 'query': query})

    async def _adapter_github_list_issues(self, owner, repository, state='open', max_results=20):
        return await github.dispatch('github_list_issues', {
            'owner': owner, 'repository': repository, 'state': state, 'max_results': max_results})

    async def _adapter_github_get_issue(self, owner, repository, number):
        return await github.dispatch('github_get_issue', {'owner': owner, 'repository': repository, 'number': number})

    async def _adapter_github_list_pull_requests(self, owner, repository, state='open', max_results=20):
        return await github.dispatch('github_list_pull_requests', {
            'owner': owner, 'repository': repository, 'state': state, 'max_results': max_results})

    async def _adapter_github_get_pull_request(self, owner, repository, number):
        return await github.dispatch('github_get_pull_request', {'owner': owner, 'repository': repository, 'number': number})


