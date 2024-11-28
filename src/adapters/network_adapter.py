from pathlib import Path
from core.interfaces import NetworkConfiguratorPort

class NetworkAdapter(NetworkConfiguratorPort):
    def setup_network(self, rootfs_path: Path):
        interfaces_config = """
            auto lo
            iface lo inet loopback

            auto eth0
            iface eth0 inet dhcp
        """
        network_dir = rootfs_path / "etc/network"
        network_dir.mkdir(parents=True, exist_ok=True)
        (network_dir / "interfaces").write_text(interfaces_config)
