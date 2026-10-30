from PIL import Image, ImageDraw

# Image dimensions
width, height = 800, 600
# Create white background
image = Image.new('RGB', (width, height), color='skyblue')
draw = ImageDraw.Draw(image)

# Draw grass field (green rectangle at bottom)
grass_height = 150
grass_top = height - grass_height
draw.rectangle([0, grass_top, width, height], fill='green')

# Draw a white soccer ball (circle)
ball_radius = 20
# Position ball near center-left, slightly above grass
ball_x = width // 3
ball_y = grass_top - ball_radius  # so ball sits on grass
draw.ellipse([ball_x - ball_radius, ball_y - ball_radius,
              ball_x + ball_radius, ball_y + ball_radius],
             fill='white', outline='black')
# Draw black pentagons on ball (simple approximation)
# We'll just draw a few lines to mimic pattern
for i in range(0, 360, 45):
    import math
    rad = math.radians(i)
    x2 = ball_x + int(0.6 * ball_radius * math.cos(rad))
    y2 = ball_y + int(0.6 * ball_radius * math.sin(rad))
    draw.line([ball_x, ball_y, x2, y2], fill='black', width=1)

# Draw stick figure kicking
# Body proportions
head_radius = 15
body_length = 80
leg_length = 70
arm_length = 60
# Position figure to the right of ball, kicking towards ball
# Base point: feet on grass
base_x = ball_x + 100  # to the right of ball
base_y = grass_top  # where feet meet grass

# Draw legs: left leg back, right leg forward (kicking)
# Left leg (back)
draw.line([(base_x - 10, base_y), (base_x - 10 - int(leg_length * 0.6), base_y - int(leg_length * 0.8))],
          fill='black', width=5)
# Right leg (kicking forward)
draw.line([(base_x + 10, base_y), (base_x + 10 + int(leg_length * 0.8), base_y - int(leg_length * 0.6))],
          fill='black', width=5)

# Draw body (vertical line up from hips)
hip_y = base_y - int(leg_length * 0.2)  # approximate hip joint
draw.line([(base_x, hip_y), (base_x, hip_y - body_length)], fill='black', width=5)

# Draw arms: one arm back, one arm forward for balance
# Left arm (back)
draw.line([(base_x - 15, hip_y - body_length * 0.3), (base_x - 15 - int(arm_length * 0.5), hip_y - body_length * 0.3 - int(arm_length * 0.5))],
          fill='black', width=4)
# Right arm (forward)
draw.line([(base_x + 15, hip_y - body_length * 0.3), (base_x + 15 + int(arm_length * 0.5), hip_y - body_length * 0.3 - int(arm_length * 0.5))],
          fill='black', width=4)

# Draw head (circle)
head_center_y = hip_y - body_length - head_radius
draw.ellipse([base_x - head_radius, head_center_y - head_radius,
              base_x + head_radius, head_center_y + head_radius],
             fill='peachpuff', outline='black')

# Optional: draw simple facial features
eye_offset = 5
draw.ellipse([base_x - eye_offset - 2, head_center_y - eye_offset - 2,
              base_x - eye_offset + 2, head_center_y - eye_offset + 2],
             fill='black')
draw.ellipse([base_x + eye_offset - 2, head_center_y - eye_offset - 2,
              base_x + eye_offset + 2, head_center_y - eye_offset + 2],
             fill='black')

# Save image
output_path = '/Users/zm/git/github/openworker/soccer_kick.png'
image.save(output_path)
print(f'Image saved to {output_path}')