# standalone_galaxy_map.py
"""
Standalone galaxy map viewer - no imports needed.
Works directly with save files.
"""

import json
import os


def load_galaxy(path=None):
    """Load galaxy data from JSON file."""
    if path is None:
        # Try to find saves directory relative to script location
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # If in game/tools, go up two levels to project root
        project_root = os.path.dirname(os.path.dirname(script_dir))
        path = os.path.join(project_root, "saves", "galaxy.json")
        
        # If that doesn't exist, try relative to current directory
        if not os.path.exists(path):
            path = os.path.join("..", "..", "saves", "galaxy.json")
        
        # If still not found, try just saves/galaxy.json
        if not os.path.exists(path):
            path = "saves/galaxy.json"
    
    if not os.path.exists(path):
        print(f"✗ File not found: {path}")
        print(f"✗ Tried looking in: {os.path.abspath(path)}")
        print(f"✗ Current directory: {os.getcwd()}")
        return None
    
    print(f"✓ Loading from: {os.path.abspath(path)}")
    with open(path, 'r') as f:
        return json.load(f)


def show_statistics(galaxy_data):
    """Display galaxy statistics."""
    sectors = galaxy_data.get('sectors', {})
    size = galaxy_data.get('size', len(sectors))
    
    port_count = sum(1 for s in sectors.values() if s.get('port'))
    stardock_count = sum(1 for s in sectors.values() if s.get('stardock'))
    planet_count = sum(1 for s in sectors.values() if s.get('planet'))
    
    total_warps = sum(len(s.get('neighbors', [])) for s in sectors.values())
    avg_warps = total_warps / len(sectors) if sectors else 0
    
    print("\n" + "=" * 60)
    print("GALAXY STATISTICS")
    print("=" * 60)
    print(f"Total Sectors:        {size}")
    print(f"Ports:                {port_count}")
    print(f"Stardocks:            {stardock_count}")
    print(f"Planets:              {planet_count}")
    print(f"Avg Warp Routes:      {avg_warps:.2f}")
    print("=" * 60)


def show_sector(galaxy_data, sector_id):
    """Show detailed sector information."""
    sectors = galaxy_data.get('sectors', {})
    sector = sectors.get(str(sector_id))
    
    if not sector:
        print(f"\n✗ Sector {sector_id} not found!")
        return
    
    print(f"\n{'=' * 60}")
    print(f"SECTOR {sector_id} DETAILS")
    print(f"{'=' * 60}")
    
    # Features
    features = []
    if sector.get('stardock'):
        features.append("🏢 STARDOCK")
    if sector.get('port'):
        port = sector['port']
        features.append(f"🏪 Port: {port.get('name', 'Unknown')}")
    if sector.get('planet'):
        features.append(f"🌍 Planet")
    
    if features:
        print("Features:")
        for feature in features:
            print(f"  {feature}")
    else:
        print("Features: (empty space)")
    
    # Warp routes
    neighbors = sector.get('neighbors', [])
    print(f"\nWarp Routes ({len(neighbors)}):")
    if neighbors:
        for neighbor_id in sorted(neighbors):
            neighbor = sectors.get(str(neighbor_id), {})
            feature_str = ""
            if neighbor.get('stardock'):
                feature_str = " [STARDOCK]"
            elif neighbor.get('port'):
                feature_str = f" [PORT: {neighbor['port'].get('name', 'Unknown')}]"
            print(f"  → Sector {neighbor_id}{feature_str}")
    else:
        print("  (none - isolated sector!)")
    
    # Port details
    if sector.get('port'):
        port = sector['port']
        print(f"\nPort: {port.get('name', 'Unknown')} (Type {port.get('type_id', '?')})")
        prices = port.get('prices', {})
        levels = port.get('commodity_levels', {})
        print(f"  Fuel:      {prices.get('fuel', '?'):4} cr | Stock: {levels.get('fuel', '?'):3}%")
        print(f"  Ore:       {prices.get('ore', '?'):4} cr | Stock: {levels.get('ore', '?'):3}%")
        print(f"  Equipment: {prices.get('equipment', '?'):4} cr | Stock: {levels.get('equipment', '?'):3}%")
    
    print("=" * 60)


def show_stardocks(galaxy_data):
    """List all stardocks."""
    sectors = galaxy_data.get('sectors', {})
    stardocks = [sid for sid, s in sectors.items() if s.get('stardock')]
    
    print("\n" + "=" * 60)
    print(f"STARDOCKS ({len(stardocks)} total)")
    print("=" * 60)
    
    if not stardocks:
        print("✗ NO STARDOCKS FOUND!")
        print("  This is a bug - sector 2 should always have a stardock!")
    else:
        for sid in sorted(stardocks, key=int):
            sector = sectors[sid]
            neighbors = sector.get('neighbors', [])
            print(f"\nSector {sid}: 🏢 STARDOCK (Celestial Bazaar)")
            print(f"  Warp routes: {len(neighbors)}")
            print(f"  Connected to: {', '.join(map(str, sorted(neighbors)))}")
    
    print("=" * 60)


def show_ports(galaxy_data):
    """List all ports."""
    sectors = galaxy_data.get('sectors', {})
    ports = [(sid, s) for sid, s in sectors.items() if s.get('port')]
    ports.sort(key=lambda x: int(x[0]))
    
    print("\n" + "=" * 60)
    print(f"ALL PORTS ({len(ports)} total)")
    print("=" * 60)
    
    for sid, sector in ports:
        port = sector['port']
        print(f"\nSector {sid:3}: {port.get('name', 'Unknown')} (Type {port.get('type_id', '?')})")
        prices = port.get('prices', {})
        print(f"  Fuel: {prices.get('fuel', '?'):3} cr")
        print(f"  Ore:  {prices.get('ore', '?'):3} cr")
        print(f"  Equip: {prices.get('equipment', '?'):3} cr")
    
    print("=" * 60)


def find_route(galaxy_data, start, end, max_hops=10):
    """Find shortest route between sectors using BFS."""
    sectors = galaxy_data.get('sectors', {})
    
    if str(start) not in sectors:
        print(f"\n✗ Start sector {start} does not exist!")
        return
    if str(end) not in sectors:
        print(f"\n✗ End sector {end} does not exist!")
        return
    
    print(f"\n{'=' * 60}")
    print(f"ROUTE: Sector {start} → Sector {end}")
    print("=" * 60)
    
    # BFS
    queue = [(start, [start])]
    visited = {start}
    
    while queue:
        current, path = queue.pop(0)
        
        if current == end:
            print(f"\nShortest route found ({len(path) - 1} warps):")
            for i, sid in enumerate(path):
                sector = sectors.get(str(sid), {})
                features = []
                if sector.get('stardock'):
                    features.append("STARDOCK")
                if sector.get('port'):
                    features.append(f"Port: {sector['port'].get('name', 'Unknown')}")
                
                feature_str = f" ({', '.join(features)})" if features else ""
                if i == 0:
                    print(f"  START: Sector {sid}{feature_str}")
                elif i == len(path) - 1:
                    print(f"  END:   Sector {sid}{feature_str}")
                else:
                    print(f"  {i:2}.     Sector {sid}{feature_str}")
            print("=" * 60)
            return
        
        if len(path) >= max_hops:
            continue
        
        sector = sectors.get(str(current), {})
        for neighbor in sector.get('neighbors', []):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor]))
    
    print(f"\n✗ No route found within {max_hops} warps!")
    print("=" * 60)


def interactive_mode(galaxy_data):
    """Run interactive command loop."""
    print("\n" + "=" * 60)
    print("TRADEWARS 2025 - GALAXY MAP TOOL")
    print("=" * 60)
    print("\nCommands:")
    print("  stats                  - Show galaxy statistics")
    print("  sector <id>            - Show sector details")
    print("  ports                  - List all ports")
    print("  stardocks              - List all stardocks")
    print("  route <start> <end>    - Find route between sectors")
    print("  quit                   - Exit tool")
    print("=" * 60)
    
    while True:
        try:
            cmd = input("\nMap > ").strip().lower()
            
            if not cmd:
                continue
            
            parts = cmd.split()
            
            if parts[0] in ('quit', 'exit', 'q'):
                print("\nExiting map tool.")
                break
            
            elif parts[0] == 'stats':
                show_statistics(galaxy_data)
            
            elif parts[0] == 'sector' and len(parts) == 2:
                try:
                    sid = int(parts[1])
                    show_sector(galaxy_data, sid)
                except ValueError:
                    print("✗ Invalid sector ID")
            
            elif parts[0] == 'ports':
                show_ports(galaxy_data)
            
            elif parts[0] == 'stardocks':
                show_stardocks(galaxy_data)
            
            elif parts[0] == 'route' and len(parts) == 3:
                try:
                    start = int(parts[1])
                    end = int(parts[2])
                    find_route(galaxy_data, start, end)
                except ValueError:
                    print("✗ Invalid sector IDs")
            
            else:
                print("✗ Unknown command")
        
        except KeyboardInterrupt:
            print("\n\nExiting map tool.")
            break
        except Exception as e:
            print(f"✗ Error: {e}")


def main():
    """Main entry point."""
    import sys
    
    save_path = None  # Will auto-detect
    
    # Parse simple arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == '--help':
            print("Usage: python standalone_galaxy_map.py [options]")
            print("\nOptions:")
            print("  --stats              Show statistics")
            print("  --stardocks          List stardocks")
            print("  --ports              List ports")
            print("  --sector <id>        Show sector details")
            print("  --save <path>        Use specific save file")
            print("\nRun without options for interactive mode")
            return
        
        if '--save' in sys.argv:
            idx = sys.argv.index('--save')
            if idx + 1 < len(sys.argv):
                save_path = sys.argv[idx + 1]
    
    galaxy_data = load_galaxy(save_path)
    if not galaxy_data:
        print("\n✗ Could not load galaxy data!")
        print("  Make sure the server has been run at least once to create saves/")
        return
    
    # Handle command-line options
    if '--stats' in sys.argv:
        show_statistics(galaxy_data)
    elif '--stardocks' in sys.argv:
        show_stardocks(galaxy_data)
    elif '--ports' in sys.argv:
        show_ports(galaxy_data)
    elif '--sector' in sys.argv:
        idx = sys.argv.index('--sector')
        if idx + 1 < len(sys.argv):
            try:
                sector_id = int(sys.argv[idx + 1])
                show_sector(galaxy_data, sector_id)
            except ValueError:
                print("✗ Invalid sector ID")
    else:
        # Interactive mode
        interactive_mode(galaxy_data)


if __name__ == '__main__':
    main()