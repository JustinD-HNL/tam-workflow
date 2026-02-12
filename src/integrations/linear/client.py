"""Linear GraphQL API client."""

from typing import Optional

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from src.integrations.base import IntegrationClient, IntegrationError
from src.models.integration import IntegrationType

logger = structlog.get_logger()

LINEAR_API_URL = "https://api.linear.app/graphql"


class LinearClient(IntegrationClient):
    integration_type = IntegrationType.LINEAR

    async def _request(self, query: str, variables: Optional[dict] = None) -> dict:
        """Execute a GraphQL request against Linear API."""
        token = await self.get_access_token()
        async with httpx.AsyncClient() as client:
            response = await client.post(
                LINEAR_API_URL,
                json={"query": query, "variables": variables or {}},
                headers={
                    "Authorization": token,
                    "Content-Type": "application/json",
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            if "errors" in data:
                logger.error("linear.graphql_error", errors=data["errors"])
                raise IntegrationError(f"Linear API error: {data['errors']}")
            return data.get("data", {})

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def create_issue(
        self,
        title: str,
        description: str = "",
        team_id: Optional[str] = None,
        project_id: Optional[str] = None,
        assignee_id: Optional[str] = None,
        priority: int = 0,
        label_ids: Optional[list[str]] = None,
    ) -> dict:
        """Create a new Linear issue."""
        query = """
        mutation IssueCreate($input: IssueCreateInput!) {
            issueCreate(input: $input) {
                success
                issue {
                    id
                    identifier
                    title
                    url
                    state { name }
                }
            }
        }
        """
        input_data = {"title": title, "description": description}
        if team_id:
            input_data["teamId"] = team_id
        if project_id:
            input_data["projectId"] = project_id
        if assignee_id:
            input_data["assigneeId"] = assignee_id
        if priority:
            input_data["priority"] = priority
        if label_ids:
            input_data["labelIds"] = label_ids

        data = await self._request(query, {"input": input_data})
        result = data.get("issueCreate", {})
        if not result.get("success"):
            raise IntegrationError("Failed to create Linear issue")

        issue = result.get("issue", {})
        logger.info("linear.issue_created", identifier=issue.get("identifier"), title=title)
        return issue

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def update_issue(self, issue_id: str, **kwargs) -> dict:
        """Update an existing Linear issue."""
        query = """
        mutation IssueUpdate($id: String!, $input: IssueUpdateInput!) {
            issueUpdate(id: $id, input: $input) {
                success
                issue {
                    id
                    identifier
                    title
                    url
                    state { name }
                }
            }
        }
        """
        data = await self._request(query, {"id": issue_id, "input": kwargs})
        result = data.get("issueUpdate", {})
        if not result.get("success"):
            raise IntegrationError(f"Failed to update Linear issue {issue_id}")
        return result.get("issue", {})

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def list_project_issues(
        self,
        project_id: str,
        limit: int = 50,
        include_completed: bool = False,
    ) -> list[dict]:
        """List issues in a Linear project."""
        filter_clause = ""
        if not include_completed:
            filter_clause = ', filter: { state: { type: { nin: ["completed", "canceled"] } } }'

        query = f"""
        query ProjectIssues($projectId: String!, $first: Int!) {{
            project(id: $projectId) {{
                issues(first: $first{filter_clause}) {{
                    nodes {{
                        id
                        identifier
                        title
                        description
                        url
                        priority
                        state {{ name type }}
                        assignee {{ name }}
                        labels {{ nodes {{ name }} }}
                        createdAt
                        updatedAt
                    }}
                }}
            }}
        }}
        """
        data = await self._request(query, {"projectId": project_id, "first": limit})
        return data.get("project", {}).get("issues", {}).get("nodes", [])

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def list_teams(self) -> list[dict]:
        """List all teams (useful for setup/config)."""
        query = """
        query { teams { nodes { id name key } } }
        """
        data = await self._request(query)
        return data.get("teams", {}).get("nodes", [])

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def list_projects(self, team_id: Optional[str] = None) -> list[dict]:
        """List projects (optionally filtered by team)."""
        if team_id:
            query = """
            query($teamId: String!) {
                team(id: $teamId) {
                    projects { nodes { id name state } }
                }
            }
            """
            data = await self._request(query, {"teamId": team_id})
            return data.get("team", {}).get("projects", {}).get("nodes", [])
        else:
            query = """
            query { projects { nodes { id name state } } }
            """
            data = await self._request(query)
            return data.get("projects", {}).get("nodes", [])

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_project(self, project_id: str) -> dict:
        """Get a project by ID to verify it exists."""
        query = """
        query($id: String!) {
            project(id: $id) {
                id name description state
                teams { nodes { id name } }
            }
        }
        """
        data = await self._request(query, {"id": project_id})
        project = data.get("project")
        if not project:
            raise IntegrationError(f"Linear project not found: {project_id}")
        return project

    async def find_team_by_name(self, name: str) -> Optional[dict]:
        """Find a team by name or key (case-insensitive)."""
        teams = await self.list_teams()
        name_lower = name.lower()
        for team in teams:
            if team.get("name", "").lower() == name_lower:
                return team
            if team.get("key", "").lower() == name_lower:
                return team
        return None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def list_users(self) -> list[dict]:
        """List all workspace users with pagination."""
        all_users = []
        cursor = None
        while True:
            if cursor:
                query = """
                query($cursor: String) {
                    users(first: 100, after: $cursor) {
                        nodes { id name email displayName active }
                        pageInfo { hasNextPage endCursor }
                    }
                }
                """
                data = await self._request(query, {"cursor": cursor})
            else:
                query = """
                query {
                    users(first: 100) {
                        nodes { id name email displayName active }
                        pageInfo { hasNextPage endCursor }
                    }
                }
                """
                data = await self._request(query)
            users_data = data.get("users", {})
            all_users.extend(users_data.get("nodes", []))
            page_info = users_data.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break
            cursor = page_info.get("endCursor")
        return all_users

    async def find_user(self, query_str: str) -> Optional[dict]:
        """Find a user by name or email (case-insensitive partial match)."""
        users = await self.list_users()
        q = query_str.lower().strip()
        for user in users:
            if not user.get("active", True):
                continue
            if q == user.get("email", "").lower():
                return user
            if q == user.get("name", "").lower():
                return user
            if q == user.get("displayName", "").lower():
                return user
            # Partial match
            if q in user.get("name", "").lower() or q in user.get("email", "").lower():
                return user
        return None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_issue(self, issue_id: str) -> dict:
        """Get a single issue by ID."""
        query = """
        query($id: String!) {
            issue(id: $id) {
                id identifier title description url priority
                state { name type }
                assignee { name id }
                labels { nodes { name id } }
                project { id name }
                createdAt updatedAt
            }
        }
        """
        data = await self._request(query, {"id": issue_id})
        return data.get("issue", {})
