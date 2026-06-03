from PIL import Image

img_path = r'C:\Users\12546\AppData\Local\hermes\scripts\qq_qr_display.png'
try:
    img = Image.open(img_path)
    # Resize for terminal display - make it wider for better visibility
    width = 50
    height = int(img.height * width / img.width * 0.5)
    img = img.resize((width, height)).convert('L')
    
    # Invert and use block characters
    chars = [' ', '░', '▒', '▓', '█']
    
    print('\n' + '=' * 60)
    print('  请用手机QQ扫描下方二维码登录')
    print('=' * 60)
    
    for y in range(img.height):
        line = ''
        for x in range(img.width):
            pixel = img.getpixel((x, y))
            idx = min(pixel // 51, 4)
            line += chars[idx]
        print(line)
    
    print('=' * 60)
    print('  打开手机QQ → 扫一扫 → 扫描上方二维码')
    print('=' * 60 + '\n')
    
except Exception as e:
    print(f'Error: {e}')