use rand::Rng;
use crate::tile::Tile;
use crate::tile_registry::TileRegistry;

#[derive(Clone)]
pub struct Room {
    pub x: usize,
    pub y: usize,
    pub width: usize,
    pub height: usize,
}

#[derive(Clone)]
pub struct Dungeon {
    pub width: usize,
    pub height: usize,
    pub tiles: Vec<Vec<Tile>>,
    pub rooms: Vec<Room>,
}

impl Dungeon {
    pub fn new_with_registry(width: usize, height: usize, registry: &TileRegistry) -> Self {
        Self::new_with_room_count(width, height, registry, 8, 12)
    }
    
    pub fn new_with_room_count(width: usize, height: usize, registry: &TileRegistry, min_rooms: u32, max_rooms: u32) -> Self {
        // Get all wall tiles from registry, default to wall_dirt_top if none found
        let wall_tiles = registry.get_wall_tiles();
        let default_wall = if wall_tiles.is_empty() {
            registry.get_wall_dirt_top()
        } else {
            // Use first wall tile as default
            wall_tiles[0].clone()
        };
        
        let mut tiles = vec![vec![default_wall; width]; height];
        let rooms = Self::generate_rooms(&mut tiles, width, height, registry, min_rooms, max_rooms);
        Self { width, height, tiles, rooms }
    }

    fn generate_rooms(tiles: &mut Vec<Vec<Tile>>, width: usize, height: usize, registry: &TileRegistry, min_rooms: u32, max_rooms: u32) -> Vec<Room> {
        let mut rng = rand::thread_rng();
        // Generate rooms based on level config
        let num_rooms = rng.gen_range(min_rooms..=max_rooms) as usize;
        let mut rooms: Vec<Room> = Vec::new();
        const MAX_ATTEMPTS: usize = 200; // Limit attempts to avoid infinite loops

        // Generate rooms with varied sizes (some bigger) and allow them to be closer together
        let mut attempts = 0;
        while rooms.len() < num_rooms && attempts < MAX_ATTEMPTS {
            attempts += 1;
            
            // Vary room sizes: 30% chance for large rooms (10-15), 70% for normal (5-10)
            let (room_width, room_height) = if rng.gen_bool(0.3) {
                // Large room
                (rng.gen_range(10..=15), rng.gen_range(10..=15))
            } else {
                // Normal room
                (rng.gen_range(5..=10), rng.gen_range(5..=10))
            };
            
            let x = rng.gen_range(1..(width - room_width - 1));
            let y = rng.gen_range(1..(height - room_height - 1));

            let room = Room {
                x,
                y,
                width: room_width,
                height: room_height,
            };
            
            // Check for overlaps - allow rooms to be closer (minimum 2 tile gap instead of complete separation)
            let min_gap = 2; // Minimum gap between rooms
            let mut overlaps = false;
            for existing_room in &rooms {
                // Check if rooms are too close (with minimum gap)
                let gap_x = if x + room_width + min_gap < existing_room.x {
                    false // Room is to the left with enough gap
                } else if existing_room.x + existing_room.width + min_gap < x {
                    false // Room is to the right with enough gap
                } else {
                    true // Rooms overlap horizontally or too close
                };
                
                let gap_y = if y + room_height + min_gap < existing_room.y {
                    false // Room is above with enough gap
                } else if existing_room.y + existing_room.height + min_gap < y {
                    false // Room is below with enough gap
                } else {
                    true // Rooms overlap vertically or too close
                };
                
                if gap_x && gap_y {
                    overlaps = true;
                    break;
                }
            }

            if !overlaps {
                // Carve out oval/elliptical room using all walkable tiles from registry
                let floor_tiles = registry.get_walkable_tiles();
                
                // Calculate ellipse center and radii
                let center_x = x as f32 + room_width as f32 / 2.0;
                let center_y = y as f32 + room_height as f32 / 2.0;
                let radius_x = room_width as f32 / 2.0;
                let radius_y = room_height as f32 / 2.0;
                
                // Carve out oval shape
                if !floor_tiles.is_empty() {
                    for dy in 0..room_height {
                        for dx in 0..room_width {
                            // Check if point is inside ellipse: ((x-cx)^2/rx^2) + ((y-cy)^2/ry^2) <= 1
                            let px = x as f32 + dx as f32 + 0.5;
                            let py = y as f32 + dy as f32 + 0.5;
                            let dx_norm = (px - center_x) / radius_x;
                            let dy_norm = (py - center_y) / radius_y;
                            let dist_sq = dx_norm * dx_norm + dy_norm * dy_norm;
                            
                            // Only carve if inside ellipse (with slight margin for smoother edges)
                            if dist_sq <= 1.0 {
                                // Randomly select from all available floor tiles
                                let floor_idx = rng.gen_range(0..floor_tiles.len());
                                let mut tile = floor_tiles[floor_idx].clone();
                                // Randomize sprite if tile has multiple sprites
                                tile.randomize_sprite();
                                tiles[y + dy][x + dx] = tile;
                            }
                        }
                    }
                } else {
                    // Fallback: use default floor if no walkable tiles found
                    let mut default_floor = registry.get_floor_dark();
                    default_floor.randomize_sprite();
                    for dy in 0..room_height {
                        for dx in 0..room_width {
                            // Check if point is inside ellipse
                            let px = x as f32 + dx as f32 + 0.5;
                            let py = y as f32 + dy as f32 + 0.5;
                            let dx_norm = (px - center_x) / radius_x;
                            let dy_norm = (py - center_y) / radius_y;
                            let dist_sq = dx_norm * dx_norm + dy_norm * dy_norm;
                            
                            if dist_sq <= 1.0 {
                                tiles[y + dy][x + dx] = default_floor.clone();
                                tiles[y + dy][x + dx].randomize_sprite();
                            }
                        }
                    }
                }
                rooms.push(room);
            }
        }
        
        // Connect rooms with corridors using minimum spanning tree (MST) for shorter paths
        // This ensures all rooms are connected with minimal total path length
        if rooms.len() > 1 {
            let floor_tiles = registry.get_walkable_tiles();
            let default_floor = if floor_tiles.is_empty() {
                registry.get_floor_dark()
            } else {
                floor_tiles[0].clone()
            };
            
            // Calculate distances between all room pairs
            let mut distances: Vec<(usize, usize, usize)> = Vec::new();
            for i in 0..rooms.len() {
                for j in (i + 1)..rooms.len() {
                    let center1_x = rooms[i].x + rooms[i].width / 2;
                    let center1_y = rooms[i].y + rooms[i].height / 2;
                    let center2_x = rooms[j].x + rooms[j].width / 2;
                    let center2_y = rooms[j].y + rooms[j].height / 2;
                    
                    // Use Manhattan distance (L1) for path length estimation
                    let dx = if center1_x > center2_x { center1_x - center2_x } else { center2_x - center1_x };
                    let dy = if center1_y > center2_y { center1_y - center2_y } else { center2_y - center1_y };
                    let distance = dx + dy;
                    
                    distances.push((i, j, distance));
                }
            }
            
            // Sort by distance (shortest first)
            distances.sort_by_key(|&(_, _, dist)| dist);
            
            // Use Union-Find (Disjoint Set Union) for MST
            let mut parent: Vec<usize> = (0..rooms.len()).collect();
            
            fn find(parent: &mut [usize], x: usize) -> usize {
                if parent[x] != x {
                    parent[x] = find(parent, parent[x]);
                }
                parent[x]
            }
            
            fn union(parent: &mut [usize], x: usize, y: usize) -> bool {
                let root_x = find(parent, x);
                let root_y = find(parent, y);
                if root_x != root_y {
                    parent[root_y] = root_x;
                    true
                } else {
                    false
                }
            }
            
            // Build MST: connect rooms with shortest paths first
            for (i, j, _) in distances {
                if union(&mut parent, i, j) {
                    // Connect these two rooms
                    let room1 = &rooms[i];
                    let room2 = &rooms[j];
                    
                    let center1_x = room1.x + room1.width / 2;
                    let center1_y = room1.y + room1.height / 2;
                    let center2_x = room2.x + room2.width / 2;
                    let center2_y = room2.y + room2.height / 2;
                    
                    // L-shaped corridor (choose direction that minimizes path)
                    let dx = if center2_x > center1_x { center2_x - center1_x } else { center1_x - center2_x };
                    let dy = if center2_y > center1_y { center2_y - center1_y } else { center1_y - center2_y };
                    
                    // Choose direction that creates shorter path
                    if dx < dy {
                        // Horizontal then vertical
                        let start_x = center1_x.min(center2_x);
                        let end_x = center1_x.max(center2_x);
                        for x in start_x..=end_x {
                            if center1_y < tiles.len() && x < tiles[0].len() {
                                let mut tile = if !floor_tiles.is_empty() {
                                    let floor_idx = rng.gen_range(0..floor_tiles.len());
                                    floor_tiles[floor_idx].clone()
                                } else {
                                    default_floor.clone()
                                };
                                tile.randomize_sprite();
                                tiles[center1_y][x] = tile;
                            }
                        }
                        let start_y = center1_y.min(center2_y);
                        let end_y = center1_y.max(center2_y);
                        for y in start_y..=end_y {
                            if y < tiles.len() && center2_x < tiles[0].len() {
                                let mut tile = if !floor_tiles.is_empty() {
                                    let floor_idx = rng.gen_range(0..floor_tiles.len());
                                    floor_tiles[floor_idx].clone()
                                } else {
                                    default_floor.clone()
                                };
                                tile.randomize_sprite();
                                tiles[y][center2_x] = tile;
                            }
                        }
                    } else {
                        // Vertical then horizontal
                        let start_y = center1_y.min(center2_y);
                        let end_y = center1_y.max(center2_y);
                        for y in start_y..=end_y {
                            if y < tiles.len() && center1_x < tiles[0].len() {
                                let mut tile = if !floor_tiles.is_empty() {
                                    let floor_idx = rng.gen_range(0..floor_tiles.len());
                                    floor_tiles[floor_idx].clone()
                                } else {
                                    default_floor.clone()
                                };
                                tile.randomize_sprite();
                                tiles[y][center1_x] = tile;
                            }
                        }
                        let start_x = center1_x.min(center2_x);
                        let end_x = center1_x.max(center2_x);
                        for x in start_x..=end_x {
                            if center2_y < tiles.len() && x < tiles[0].len() {
                                let mut tile = if !floor_tiles.is_empty() {
                                    let floor_idx = rng.gen_range(0..floor_tiles.len());
                                    floor_tiles[floor_idx].clone()
                                } else {
                                    default_floor.clone()
                                };
                                tile.randomize_sprite();
                                tiles[center2_y][x] = tile;
                            }
                        }
                    }
                }
            }
        }
        
        rooms
    }

    pub fn is_walkable(&self, x: usize, y: usize) -> bool {
        if y >= self.height || x >= self.width {
            return false;
        }
        self.tiles[y][x].walkable
    }
}

