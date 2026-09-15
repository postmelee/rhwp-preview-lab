"""A fork publish grant is scoped to one dispatch, repository, PR and SHA."""
import re


def fork(pr):
    head = pr.get('head', {}).get('repo')
    base = pr.get('base', {}).get('repo')
    if not head or not base:
        raise ValueError('PR repository identity unavailable')
    return head['id'] != base['id']


def grant(pr, number, sha, actors, permission):
    if not re.fullmatch('[a-f0-9]{40}', sha) or pr['head']['sha'] != sha:
        raise ValueError('approval SHA must equal current full PR head SHA')
    if pr['state'] != 'open' or not fork(pr):
        raise ValueError('approval requires an open fork PR')
    for actor in set(actors):
        if not actor or permission(actor) not in ('write', 'maintain', 'admin'):
            raise ValueError('fork approval requires current maintainer permission')
    return {'number': number, 'sha': sha, 'repository_id': pr['head']['repo']['id'], 'actors': actors}


def enforce(pr, number, sha, approval, permission):
    if not fork(pr):
        return
    if not approval:
        raise ValueError('fork preview awaiting maintainer approval for current SHA')
    expected = (number, sha, pr['head']['repo']['id'])
    if (approval['number'], approval['sha'], approval['repository_id']) != expected:
        raise ValueError('fork approval does not match current PR repository and SHA')
    # Includes live head and current actor permissions, not merely original dispatch inputs.
    grant(pr, number, sha, approval['actors'], permission)
