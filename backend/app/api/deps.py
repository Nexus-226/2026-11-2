from app.agent.runtime import AgentRuntime
from app.agent.tools import build_tool_allowlist
from app.services.nearby_service import NearbyService
from app.services.pet_service import PetService

pet_service = PetService()
nearby_service = NearbyService()
agent_runtime = AgentRuntime(build_tool_allowlist(pet_service))
