import asyncio
import os
import shutil
import time
from playwright.async_api import async_playwright
from google.cloud import storage

BUCKET_NAME = "runlifestyle-images-qwiklabs-gcp-02-61a3e08edf96"

async def record_demo():
    output_dir = "recordings"
    os.makedirs(output_dir, exist_ok=True)
    
    url = "https://runlifestyle-frontend-199686373659.us-east1.run.app"
    print(f"Opening {url}...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            record_video_dir=output_dir,
            record_video_size={"width": 1280, "height": 800}
        )
        page = await context.new_page()
        
        # 1. Open app and start lo-fi music
        await page.goto(url, wait_until="networkidle")
        await asyncio.sleep(1)
        print("Starting upbeat lo-fi background music...")
        await page.locator("#musicBtn").click()
        await asyncio.sleep(2)
        
        # 2. Click 1st prompt chip: Parques no Tatuapé (shows core running route search)
        print("Clicking prompt 1: Parques no Tatuapé...")
        chip1 = page.locator(".example-chip", has_text="Parques no Tatuapé")
        await chip1.click()
        await asyncio.sleep(12) # wait for agent response
        
        # 3. Type 2nd prompt: Richer tool call + image generation
        print("Sending prompt 2: Generate route artwork...")
        input_box = page.locator("#input")
        await input_box.fill("Gere uma imagem vibrante da melhor rota para correr no Parque do Carmo com sol e vegetação")
        await page.locator("button", has_text="Enviar").click()
        await asyncio.sleep(18) # wait for tool execution & artwork generation
        
        await asyncio.sleep(3)
        
        # Close context to flush video
        video_path = await page.video.path()
        await context.close()
        await browser.close()
        
        print(f"Recorded video saved to: {video_path}")
        
        # Copy to demo_video.webm and upload to GCS bucket
        dest_filename = "runlifestyle_demo.webm"
        shutil.copy(video_path, dest_filename)
        
        try:
            client = storage.Client(project="qwiklabs-gcp-02-61a3e08edf96")
            bucket = client.bucket(BUCKET_NAME)
            blob = bucket.blob(dest_filename)
            blob.upload_from_filename(dest_filename, content_type="video/webm")
            public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{dest_filename}"
            print(f"Uploaded demo video to GCS: {public_url}")
        except Exception as e:
            print(f"Failed to upload to GCS: {e}")

if __name__ == "__main__":
    asyncio.run(record_demo())
