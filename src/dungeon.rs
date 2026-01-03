use rand::Rng;
use crate::tile::Tile;
use crate::tile_registry::TileRegistry;

#[derive(Clone)]
pub struct Dungeon {
    pub width: usize,
    pub height: usize,
    pub tiles: Vec<Vec<Tile>>,
}

impl Dungeon {
    pub fn new_with_registry(width: usize, height: usize, registry: &TileRegistry) -> Self {
        let mut tiles = vec![vec![registry.get_wall_dirt_top(); width]; height];
        Self::generate_rooms(&mut tiles, width, height, registry);
        Self { width, height, tiles }
    }

    fn generate_rooms(tiles: &mut Vec<Vec<Tile>>, width: usize, height: usize, registry: &TileRegistry) {
        let mut rng = rand::thread_rng();
        let num_rooms = rng.gen_range(5..=10);
        let mut rooms = Vec::new();

        // Generate rooms
        for _ in 0..num_rooms {
            let room_width = rng.gen_range(4..=8);
            let room_height = rng.gen_range(4..=8);
            let x = rng.gen_range(1..(width - room_width - 1));
            let y = rng.gen_range(1..(height - room_height - 1));

            let room = (x, y, room_width, room_height);
            
            // Check for overlaps (simple check)
            let mut overlaps = false;
            for (rx, ry, rw, rh) in &rooms {
                if !(x + room_width < *rx || *rx + *rw < x || 
                     y + room_height < *ry || *ry + *rh < y) {
                    overlaps = true;
                    break;
                }
            }

            if !overlaps {
                // Carve out room with random floor variations
                // Each tile will randomize its sprite from the GameObject's sprite array
                let floor_tiles = vec![
                    registry.get_floor_dark(),
                    registry.get_floor_stone(),  // This has multiple sprites that randomize
                ];
                for dy in 0..room_height {
                    for dx in 0..room_width {
                        let floor_idx = rng.gen_range(0..floor_tiles.len());
                        let mut tile = floor_tiles[floor_idx].clone();
                        // Randomize sprite if tile has multiple sprites
                        tile.randomize_sprite();
                        tiles[y + dy][x + dx] = tile;
                    }
                }
                rooms.push(room);
            }
        }

        // Connect rooms with corridors
        for i in 0..rooms.len() - 1 {
            let (x1, y1, w1, h1) = rooms[i];
            let (x2, y2, w2, h2) = rooms[i + 1];
            
            let center1_x = x1 + w1 / 2;
            let center1_y = y1 + h1 / 2;
            let center2_x = x2 + w2 / 2;
            let center2_y = y2 + h2 / 2;

            // L-shaped corridor
            let floor_tiles = vec![
                registry.get_floor_dark(),
                registry.get_floor_stone(),  // This has multiple sprites that randomize
            ];
            
            if rng.gen_bool(0.5) {
                // Horizontal then vertical
                let start_x = center1_x.min(center2_x);
                let end_x = center1_x.max(center2_x);
                for x in start_x..=end_x {
                    if center1_y < tiles.len() && x < tiles[0].len() {
                        let floor_idx = rng.gen_range(0..floor_tiles.len());
                        let mut tile = floor_tiles[floor_idx].clone();
                        tile.randomize_sprite();
                        tiles[center1_y][x] = tile;
                    }
                }
                let start_y = center1_y.min(center2_y);
                let end_y = center1_y.max(center2_y);
                for y in start_y..=end_y {
                    if y < tiles.len() && center2_x < tiles[0].len() {
                        let floor_idx = rng.gen_range(0..floor_tiles.len());
                        let mut tile = floor_tiles[floor_idx].clone();
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
                        let floor_idx = rng.gen_range(0..floor_tiles.len());
                        let mut tile = floor_tiles[floor_idx].clone();
                        tile.randomize_sprite();
                        tiles[y][center1_x] = tile;
                    }
                }
                let start_x = center1_x.min(center2_x);
                let end_x = center1_x.max(center2_x);
                for x in start_x..=end_x {
                    if center2_y < tiles.len() && x < tiles[0].len() {
                        let floor_idx = rng.gen_range(0..floor_tiles.len());
                        let mut tile = floor_tiles[floor_idx].clone();
                        tile.randomize_sprite();
                        tiles[center2_y][x] = tile;
                    }
                }
            }
        }
    }

    pub fn is_walkable(&self, x: usize, y: usize) -> bool {
        if y >= self.height || x >= self.width {
            return false;
        }
        self.tiles[y][x].walkable
    }
}

