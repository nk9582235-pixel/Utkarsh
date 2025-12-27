"""
Utkarsh Video Downloader Module
Wrapper for downloading videos with yt-dlp/aria2c
"""

import os
import re
import subprocess
import requests
import logging
from pathlib import Path

try:
    import yt_dlp as youtube_dl
except ImportError:
    import youtube_dl

logger = logging.getLogger(__name__)


class UtkarshDownloader:
    """Download videos from URLs"""
    
    def __init__(self, download_path="./downloads"):
        self.download_path = Path(download_path)
        self.download_path.mkdir(parents=True, exist_ok=True)
        
    def sanitize_filename(self, filename):
        """Clean filename for Windows compatibility"""
        # Remove invalid characters
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        filename = filename.replace('\n', ' ').replace('\r', ' ')
        filename = ' '.join(filename.split())
        # Limit length
        if len(filename) > 150:
            filename = filename[:150]
        return filename.strip() or "video"
    
    def download_video(self, title, url):
        """
        Download a video and return the file path
        Returns: file_path or None
        """
        try:
            safe_title = self.sanitize_filename(title)
            output_path = self.download_path / safe_title
            
            # Check if YouTube URL
            if 'youtube.com' in url or 'youtu.be' in url:
                return self._download_youtube(url, output_path, title)
            
            # Try direct download with aria2c first
            result = self._download_aria2c(url, output_path, title)
            if result:
                return result
            
            # Fallback to yt-dlp
            result = self._download_ytdlp(url, output_path, title)
            if result:
                return result
            
            # Last fallback: direct requests
            result = self._download_direct(url, output_path, title)
            if result:
                return result
            
            return None
            
        except Exception as e:
            logger.error(f"Download error for {title}: {e}")
            return None
    
    def _download_youtube(self, url, output_path, title):
        """Download YouTube video"""
        try:
            ydl_opts = {
                'outtmpl': str(output_path.with_suffix('.%(ext)s')),
                'format': 'bv*+ba/best[ext=mp4]/best',
                'quiet': True,
                'no_warnings': True,
                'ignoreerrors': False,
                'nocheckcertificate': True,
                'merge_output_format': 'mp4',
                # Use cookies.txt if exists
                'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None,
            }
            
            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            # Find the downloaded file
            for ext in ['.mp4', '.mkv', '.webm']:
                check_path = output_path.with_suffix(ext)
                if check_path.exists():
                    return str(check_path)
            
            return None
            
        except Exception as e:
            logger.error(f"YouTube download error: {e}")
            return None
    
    def _download_aria2c(self, url, output_path, title):
        """Download using aria2c"""
        try:
            cmd = [
                'aria2c',
                '--max-connection-per-server=8',
                '--split=8',
                '--min-split-size=5M',
                '--file-allocation=trunc',
                '--console-log-level=error',
                '--continue=true',
                '--max-tries=10',
                '--retry-wait=3',
                '--timeout=60',
                '--disable-ipv6=true',
                '--header=User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0',
                '--header=Referer: https://utkarshapp.com/',
                '--dir', str(output_path.parent),
                '--out', output_path.name + '.mp4',
                url
            ]
            
            result = subprocess.run(cmd, capture_output=True, timeout=600)
            
            final_path = output_path.with_suffix('.mp4')
            if final_path.exists() and final_path.stat().st_size > 1000:
                return str(final_path)
            
            return None
            
        except FileNotFoundError:
            logger.debug("aria2c not found, using fallback")
            return None
        except Exception as e:
            logger.error(f"aria2c error: {e}")
            return None
    
    def _download_ytdlp(self, url, output_path, title):
        """Download using yt-dlp for generic URLs"""
        try:
            ydl_opts = {
                'outtmpl': str(output_path.with_suffix('.%(ext)s')),
                'format': 'best[ext=mp4]/best',
                'quiet': True,
                'no_warnings': True,
                'nocheckcertificate': True,
                'retries': 10,
                'fragment_retries': 10,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0',
                    'Referer': 'https://utkarshapp.com/',
                }
            }
            
            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            # Find the downloaded file
            for ext in ['.mp4', '.mkv', '.webm', '.ts']:
                check_path = output_path.with_suffix(ext)
                if check_path.exists():
                    return str(check_path)
            
            return None
            
        except Exception as e:
            logger.error(f"yt-dlp error: {e}")
            return None
    
    def _download_direct(self, url, output_path, title):
        """Direct download using requests"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0',
                'Referer': 'https://utkarshapp.com/',
                'Accept': '*/*',
                'Origin': 'https://utkarshapp.com',
            }
            
            response = requests.get(url, headers=headers, stream=True, timeout=300)
            response.raise_for_status()
            
            final_path = output_path.with_suffix('.mp4')
            
            with open(final_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
            
            if final_path.exists() and final_path.stat().st_size > 1000:
                return str(final_path)
            
            return None
            
        except Exception as e:
            logger.error(f"Direct download error: {e}")
            return None
