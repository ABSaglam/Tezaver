import os

# Original SVG Content strings (from view_file)

ICON_TEMPLATE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400" fill="none">
  <defs>
    <linearGradient id="icon_grad1" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:{COLOR_1_START};stop-opacity:1" />
      <stop offset="100%" style="stop-color:{COLOR_1_END};stop-opacity:1" />
    </linearGradient>
    <linearGradient id="icon_grad2" x1="100%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:{COLOR_2_START};stop-opacity:1" />
      <stop offset="100%" style="stop-color:{COLOR_2_END};stop-opacity:1" />
    </linearGradient>
    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="3" result="blur" />
      <feComposite in="SourceGraphic" in2="blur" operator="over" />
    </filter>
  </defs>

  <!-- SYMBOL (Centered) -->
  <g>
      <!-- Main Hexagon Frame (Background) -->
      <path d="M200 50 L350 125 L350 275 L200 350 L50 275 L50 125 Z" 
            stroke="url(#icon_grad1)" stroke-width="20" fill="none" filter="url(#glow)" opacity="0.9"/>
      
      <!-- Corner Dots -->
      <circle cx="200" cy="50" r="15" fill="{DOT_COLOR}" filter="url(#glow)">
        <animate attributeName="opacity" values="1;0.5;0.1;0.1" keyTimes="0;0.2;0.5;1" dur="2.4s" begin="0s" repeatCount="indefinite" />
        <animate attributeName="r" values="18;16;15;15" keyTimes="0;0.2;0.5;1" dur="2.4s" begin="0s" repeatCount="indefinite" />
      </circle>
      <circle cx="50" cy="125" r="15" fill="{DOT_COLOR}" filter="url(#glow)">
        <animate attributeName="opacity" values="1;0.5;0.1;0.1" keyTimes="0;0.2;0.5;1" dur="2.4s" begin="0.4s" repeatCount="indefinite" />
        <animate attributeName="r" values="18;16;15;15" keyTimes="0;0.2;0.5;1" dur="2.4s" begin="0.4s" repeatCount="indefinite" />
      </circle>
      <circle cx="50" cy="275" r="15" fill="{DOT_COLOR}" filter="url(#glow)">
        <animate attributeName="opacity" values="1;0.5;0.1;0.1" keyTimes="0;0.2;0.5;1" dur="2.4s" begin="0.8s" repeatCount="indefinite" />
        <animate attributeName="r" values="18;16;15;15" keyTimes="0;0.2;0.5;1" dur="2.4s" begin="0.8s" repeatCount="indefinite" />
      </circle>
      <circle cx="200" cy="350" r="15" fill="{DOT_COLOR}" filter="url(#glow)">
        <animate attributeName="opacity" values="1;0.5;0.1;0.1" keyTimes="0;0.2;0.5;1" dur="2.4s" begin="1.2s" repeatCount="indefinite" />
        <animate attributeName="r" values="18;16;15;15" keyTimes="0;0.2;0.5;1" dur="2.4s" begin="1.2s" repeatCount="indefinite" />
      </circle>
      <circle cx="350" cy="275" r="15" fill="{DOT_COLOR}" filter="url(#glow)">
        <animate attributeName="opacity" values="1;0.5;0.1;0.1" keyTimes="0;0.2;0.5;1" dur="2.4s" begin="1.6s" repeatCount="indefinite" />
        <animate attributeName="r" values="18;16;15;15" keyTimes="0;0.2;0.5;1" dur="2.4s" begin="1.6s" repeatCount="indefinite" />
      </circle>
      <circle cx="350" cy="125" r="15" fill="{DOT_COLOR}" filter="url(#glow)">
        <animate attributeName="opacity" values="1;0.5;0.1;0.1" keyTimes="0;0.2;0.5;1" dur="2.4s" begin="2.0s" repeatCount="indefinite" />
        <animate attributeName="r" values="18;16;15;15" keyTimes="0;0.2;0.5;1" dur="2.4s" begin="2.0s" repeatCount="indefinite" />
      </circle>

      <!-- Inner T Shape -->
      <path d="M100 120 L300 120 L280 160 L120 160 Z" fill="url(#icon_grad2)" filter="url(#glow)" />
      <path d="M170 160 L230 160 L220 300 L180 300 Z" fill="url(#icon_grad2)" filter="url(#glow)" />
      
      <!-- Center Core Pulse -->
      <circle cx="200" cy="200" r="25" fill="#FFFFFF">
        <animate attributeName="opacity" values="1;0.2;1" dur="3s" repeatCount="indefinite" />
        <animate attributeName="r" values="25;30;25" dur="3s" repeatCount="indefinite" />
        <animate attributeName="fill" values="#FFFFFF;{PULSE_COLOR};#FFFFFF" dur="3s" repeatCount="indefinite" />
      </circle>
  </g>
</svg>"""

LOGO_TEMPLATE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 500 100" fill="none">
  <defs>
    <!-- Gradients for Text -->
    <linearGradient id="grad2" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#FFFFFF;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#E0E0E0;stop-opacity:1" />
    </linearGradient>
    <linearGradient id="grad1" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" style="stop-color:{TEXT_GRAD_START};stop-opacity:1" />
      <stop offset="100%" style="stop-color:{TEXT_GRAD_END};stop-opacity:1" />
    </linearGradient>
    
    <!-- Gradients for Icon -->
    <linearGradient id="icon_grad1" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:{ICON_GRAD1_START};stop-opacity:1" />
      <stop offset="100%" style="stop-color:{ICON_GRAD1_END};stop-opacity:1" />
    </linearGradient>
    <linearGradient id="icon_grad2" x1="100%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:{ICON_GRAD2_START};stop-opacity:1" />
      <stop offset="100%" style="stop-color:{ICON_GRAD2_END};stop-opacity:1" />
    </linearGradient>
    
    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="2" result="blur" />
      <feComposite in="SourceGraphic" in2="blur" operator="over" />
    </filter>
  </defs>

  <!-- SYMBOL (Scaled down) -->
  <g transform="translate(0, 5) scale(0.2)">
      <path d="M200 50 L350 125 L350 275 L200 350 L50 275 L50 125 Z" 
            stroke="url(#icon_grad1)" stroke-width="20" fill="none" filter="url(#glow)" opacity="0.9"/>
      <circle cx="50" cy="125" r="15" fill="{DOT_COLOR}" />
      <circle cx="350" cy="125" r="15" fill="{DOT_COLOR}" />
      <circle cx="200" cy="350" r="15" fill="{DOT_COLOR}" />
      <circle cx="200" cy="50" r="15" fill="{DOT_COLOR}" />
      <path d="M100 120 L300 120 L280 160 L120 160 Z" fill="url(#icon_grad2)" filter="url(#glow)" />
      <path d="M170 160 L230 160 L220 300 L180 300 Z" fill="url(#icon_grad2)" filter="url(#glow)" />
      <circle cx="200" cy="200" r="25" fill="#FFFFFF" opacity="0.9">
        <animate attributeName="opacity" values="0.9;0.4;0.9" dur="3s" repeatCount="indefinite" />
      </circle>
  </g>

  <!-- TEXT Group -->
  <g transform="translate(75, 0)">
      <!-- Main Text: TEZAVER -->
      <text x="10" y="55" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif" font-weight="800" font-size="42" fill="url(#icon_grad2)" letter-spacing="1.5" filter="url(#glow)">TEZAVER</text>
      
      <!-- Sub Text: SUFFIX -->
      <text x="215" y="55" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif" font-weight="200" font-size="36" fill="url(#grad1)" letter-spacing="0">{SUFFIX_TEXT}</text>
      
      <!-- Version Text -->
      <text x="305" y="75" text-anchor="end" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif" font-size="12" fill="#888888" letter-spacing="0">by Ali Sağlam (v0.07 Çınar)</text>
  </g>
</svg>"""

# --- 1. MAC (Blue/Cyan - Original) ---
# Icon
mac_icon_svg = ICON_TEMPLATE.format(
    COLOR_1_START="#4B0082", COLOR_1_END="#00FFFF",  # Blue Indogo -> Cyan
    COLOR_2_START="#FFD700", COLOR_2_END="#FF8C00",  # Gold -> Orange (For T core as original)
    DOT_COLOR="#00FFFF",
    PULSE_COLOR="#FFFF00"
)
# Logo
mac_logo_svg = LOGO_TEMPLATE.format(
    TEXT_GRAD_START="#4facfe", TEXT_GRAD_END="#00f2fe", # Blue
    ICON_GRAD1_START="#4B0082", ICON_GRAD1_END="#00FFFF",
    ICON_GRAD2_START="#FFD700", ICON_GRAD2_END="#FF8C00",
    DOT_COLOR="#00FFFF",
    SUFFIX_TEXT="mac"
)

# --- 2. CLOUD (Orange/Amber) ---
# Theme: Warm, Energy, Server
# Colors: Red-Orange to Yellow
cloud_icon_svg = ICON_TEMPLATE.format(
    COLOR_1_START="#8B0000", COLOR_1_END="#FF4500",  # Dark Red -> Orange Red
    COLOR_2_START="#FFD700", COLOR_2_END="#FFA500",  # Gold -> Orange
    DOT_COLOR="#FF8C00", # Dark Orange
    PULSE_COLOR="#FF4500"
)

cloud_logo_svg = LOGO_TEMPLATE.format(
    TEXT_GRAD_START="#FF416C", TEXT_GRAD_END="#FF4B2B", # Red/Orange Gradient
    ICON_GRAD1_START="#8B0000", ICON_GRAD1_END="#FF4500",
    ICON_GRAD2_START="#FFD700", ICON_GRAD2_END="#FFA500",
    DOT_COLOR="#FF8C00",
    SUFFIX_TEXT="bulut"
)

# --- 3. SIM (Green/Matrix) ---
# Theme: Neon Green, Code, Matrix
# Colors: Dark Green to Neon Green
sim_icon_svg = ICON_TEMPLATE.format(
    COLOR_1_START="#006400", COLOR_1_END="#00FF00",  # Dark Green -> Lime
    COLOR_2_START="#ADFF2F", COLOR_2_END="#32CD32",  # Green Yellow -> Lime Green
    DOT_COLOR="#00FF00", # Neon Green
    PULSE_COLOR="#00FF7F" # Spring Green
)

sim_logo_svg = LOGO_TEMPLATE.format(
    TEXT_GRAD_START="#11998e", TEXT_GRAD_END="#38ef7d", # Green Gradient
    ICON_GRAD1_START="#006400", ICON_GRAD1_END="#00FF00",
    ICON_GRAD2_START="#ADFF2F", ICON_GRAD2_END="#32CD32",
    DOT_COLOR="#00FF00",
    SUFFIX_TEXT="matrix"
)

# Write files
base_path = "src/tezaver/ui/assets"

with open(f"{base_path}/tezaver_icon_mac.svg", "w") as f: f.write(mac_icon_svg)
with open(f"{base_path}/tezaver_logo_mac.svg", "w") as f: f.write(mac_logo_svg)

with open(f"{base_path}/tezaver_icon_cloud.svg", "w") as f: f.write(cloud_icon_svg)
with open(f"{base_path}/tezaver_logo_cloud.svg", "w") as f: f.write(cloud_logo_svg)

with open(f"{base_path}/tezaver_icon_sim.svg", "w") as f: f.write(sim_icon_svg)
with open(f"{base_path}/tezaver_logo_sim.svg", "w") as f: f.write(sim_logo_svg)

print("SVG assets generated successfully!")
