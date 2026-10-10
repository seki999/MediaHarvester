"""Use yt-dlp's authenticated Instagram API extraction for photo posts too."""
from yt_dlp.extractor.instagram import InstagramIE
from .security import validate_url


class InstagramMediaIE(InstagramIE):
    def __init__(self, downloader):
        super().__init__(downloader)
        self.has_images = False

    def _extract_product_media(self, product_media):
        result = super()._extract_product_media(product_media)
        if not result.get('formats'):
            candidates = result.get('thumbnails') or []
            if candidates:
                best = max(candidates, key=lambda image:
                           (image.get('width') or 0) * (image.get('height') or 0))
                validate_url(best['url'])
                result['mh_image'] = best
                self.has_images = True
        return result

    def raise_no_formats(self, message, expected=False, video_id=None):
        if not self.has_images:
            return super().raise_no_formats(message, expected=expected, video_id=video_id)
