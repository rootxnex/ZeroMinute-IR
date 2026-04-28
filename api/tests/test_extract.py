from __future__ import annotations

from services.analyzer.extract import extract_emergency_capabilities
from services.analyzer.models import SourceBundle


def _bundle(*, source: str, abi: list[dict], name: str = "Vault") -> SourceBundle:
    return SourceBundle(
        chain_id=1,
        address="0x1111111111111111111111111111111111111111",
        verified=True,
        contract_name=name,
        abi=abi,
        compiler_version="v0.8.24+commit.e11b9ed9",
        source_files={"contracts/Vault.sol": source},
        metadata={"source": "test"},
    )


def _types(items: list[dict]) -> set[str]:
    return {item["type"] for item in items}


def _names(items: list[dict]) -> set[str]:
    return {item["name"] for item in items}


def test_extract_ownable_pausable_contract():
    source = """
    contract Vault is Ownable, Pausable {
      function pause() external onlyOwner { _pause(); }
      function unpause() external onlyOwner { _unpause(); }
    }
    """
    abi = [
        {"type": "function", "name": "pause"},
        {"type": "function", "name": "unpause"},
        {"type": "function", "name": "owner"},
    ]

    result = extract_emergency_capabilities(_bundle(source=source, abi=abi))

    assert {"pause", "unpause"}.issubset(_types(result["confirmed_functions"]))
    assert "owner" in _types(result["confirmed_roles"])
    assert "No confirmed emergency control functions detected." not in result["warnings"]


def test_extract_access_control_contract():
    source = """
    contract Vault is AccessControl {
      bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");
      constructor() { _grantRole(DEFAULT_ADMIN_ROLE, msg.sender); }
      function pause() external onlyRole(PAUSER_ROLE) {}
    }
    """
    abi = [
        {"type": "function", "name": "pause"},
        {"type": "function", "name": "grantRole"},
    ]

    result = extract_emergency_capabilities(_bundle(source=source, abi=abi))

    assert "admin" in _types(result["confirmed_roles"])
    assert "pauser" in _types(result["confirmed_roles"])
    assert any("DEFAULT_ADMIN_ROLE" in check for check in result["manual_checks"])


def test_extract_upgradeable_proxy_like_contract():
    source = """
    contract ProxyAdminLike {
      address public implementation;
      function upgradeTo(address newImplementation) external onlyAdmin {
        implementation = newImplementation;
      }
      function changeAdmin(address newAdmin) external onlyAdmin {}
      function forward(bytes calldata payload) external {
        (bool ok,) = implementation.delegatecall(payload);
        require(ok, "delegatecall failed");
      }
    }
    """
    abi = [
        {"type": "function", "name": "upgradeTo"},
        {"type": "function", "name": "changeAdmin"},
    ]

    result = extract_emergency_capabilities(_bundle(source=source, abi=abi, name="ProxyAdminLike"))

    assert "upgrade_admin" in _types(result["confirmed_functions"])
    assert any("proxy/implementation" in check for check in result["manual_checks"])


def test_extract_contract_with_no_emergency_controls():
    source = """
    contract Token {
      function transfer(address to, uint256 amount) external returns (bool) {
        return true;
      }
    }
    """
    abi = [{"type": "function", "name": "transfer"}]

    result = extract_emergency_capabilities(_bundle(source=source, abi=abi, name="Token"))

    assert result["confirmed_functions"] == []
    assert "No confirmed emergency control functions detected." in result["warnings"]
    assert any("off-chain containment" in check for check in result["manual_checks"])
