"""GitHub fetcher.

Fetches a user's public GitHub profile and repositories via the GitHub REST API.
Extracts:
  - Repositories (title, stars, primary language, topics as genres).
  - Mainstream/popularity scores mapped from star counts on a log scale.
  - Overall developer stats (public repos, followers, total stars, top language, account creation year).
"""

from __future__ import annotations

import math

from ..config import settings
from ..models import MediaItem, TasteProfile
from .base import BaseFetcher, FetchError

GITHUB_API = "https://api.github.com"


def _mainstream_from_stars(stars: int | None) -> float | None:
    """Map repository star count to a 0-100 mainstream-ness score.

    0 stars -> 10.0 (niche personal project); 50k+ stars -> 100.0 (mega-mainstream).
    """
    if stars is None or stars < 0:
        return 10.0
    # Log scale: log10(1) = 0 -> 10, log10(50000) ~ 4.7 -> 100
    val = 10.0 + (math.log10(stars + 1) / 4.7) * 90.0
    return round(max(0.0, min(100.0, val)), 1)


class GitHubFetcher(BaseFetcher):
    name = "github"

    def __init__(self) -> None:
        super().__init__()
        self.session.headers.update({"Accept": "application/vnd.github.v3+json"})

    def _headers(self) -> dict[str, str]:
        headers = {}
        token = settings.GITHUB_TOKEN
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def fetch(self, username: str, **auth) -> TasteProfile:
        username = (username or "").strip()
        if not username:
            raise FetchError("Please enter a GitHub username.")

        headers = self._headers()

        # 1. Fetch user metadata
        user_url = f"{GITHUB_API}/users/{username}"
        user_data = self.get_json(user_url, headers=headers)

        display_name = user_data.get("name") or username
        prof = TasteProfile(
            platform=self.name,
            username=username,
            display_name=display_name,
        )

        public_repos = user_data.get("public_repos", 0)
        followers = user_data.get("followers", 0)
        created_at = user_data.get("created_at", "")
        created_year = created_at[:4] if created_at else ""
        bio = user_data.get("bio") or ""

        # 2. Fetch user's public repositories (up to 100 most recently pushed)
        repos_url = f"{GITHUB_API}/users/{username}/repos"
        params = {"per_page": 100, "sort": "pushed"}
        repos_data = self.get_json(repos_url, params=params, headers=headers)

        if not isinstance(repos_data, list):
            repos_data = []

        # Sort repos: own non-fork repos with stars first, then forks/others
        def _repo_sort_key(r: dict) -> tuple[int, int]:
            is_fork = 1 if r.get("fork") else 0
            stars = r.get("stargazers_count", 0) or 0
            return (is_fork, -stars)

        sorted_repos = sorted(repos_data, key=_repo_sort_key)

        total_stars = 0
        language_counts: dict[str, int] = {}

        for repo in sorted_repos:
            repo_name = repo.get("name") or "untitled"
            language = repo.get("language")
            stars = repo.get("stargazers_count", 0) or 0
            topics = repo.get("topics") or []
            html_url = repo.get("html_url")
            is_fork = repo.get("fork", False)

            if not is_fork:
                total_stars += stars

            genres = []
            if language:
                genres.append(language)
                language_counts[language] = language_counts.get(language, 0) + 1
            for t in topics:
                if t and t not in genres:
                    genres.append(t)

            prof.top_items.append(
                MediaItem(
                    title=f"{repo_name} (fork)" if is_fork else repo_name,
                    kind="repo",
                    genres=genres,
                    count=stars,
                    popularity=_mainstream_from_stars(stars),
                    url=html_url,
                )
            )

        top_lang = (
            sorted(language_counts.items(), key=lambda x: x[1], reverse=True)[0][0]
            if language_counts
            else "None"
        )

        # Stats dictionary
        prof.stats["Public repos"] = public_repos
        prof.stats["Followers"] = followers
        prof.stats["Total stars earned"] = total_stars
        prof.stats["Primary language"] = top_lang
        if created_year:
            prof.stats["Account created"] = created_year
        if bio:
            prof.stats["Bio"] = bio

        return prof
