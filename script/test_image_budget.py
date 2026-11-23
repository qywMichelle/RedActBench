import io
import struct
import unittest

from PIL import Image, ImageChops
from resume_with_image_budget import MAX_PATCHES, fit_png, patches, resize_canvas_strips


class ImageBudgetTest(unittest.TestCase):
    def test_small_image_remains_byte_identical(self):
        output = io.BytesIO()
        Image.new('RGB', (1100, 760), 'blue').save(output, format='PNG')
        data = output.getvalue()
        resized, binding = fit_png(data)
        self.assertEqual(data, resized)
        self.assertIsNone(binding)

    def test_long_canvas_fits_and_keeps_all_edges(self):
        output = io.BytesIO()
        original = Image.new('RGB', (2200, 18240), 'white')
        # Broad colored corners detect cropping of any part of the canvas.
        original.paste('red', (0, 0, 200, 200))
        original.paste('green', (2000, 0, 2200, 200))
        original.paste('blue', (0, 18040, 200, 18240))
        original.paste('black', (2000, 18040, 2200, 18240))
        original.save(output, format='PNG')
        original.close()
        resized, binding = fit_png(output.getvalue())
        width, height = struct.unpack('>II', resized[16:24])
        self.assertLessEqual(patches(width, height), MAX_PATCHES)
        self.assertAlmostEqual(width / height, 2200 / 18240, delta=.001)
        self.assertFalse(binding['cropped'])
        self.assertNotEqual(binding['original_png_sha256'], binding['transmitted_png_sha256'])
        with Image.open(io.BytesIO(resized)) as image:
            self.assertEqual(image.getpixel((10, 10)), (255, 0, 0))
            self.assertEqual(image.getpixel((width - 10, 10)), (0, 128, 0))
            self.assertEqual(image.getpixel((10, height - 10)), (0, 0, 255))
            self.assertEqual(image.getpixel((width - 10, height - 10)), (0, 0, 0))

    def test_rgba_long_canvas_fits_without_dropping_transparency(self):
        output = io.BytesIO()
        source = Image.new('RGBA', (2200, 18240), (255, 255, 255, 0))
        source.paste((255, 0, 0, 255), (0, 0, 200, 200))
        source.paste((0, 0, 255, 255), (2000, 18040, 2200, 18240))
        source.save(output, format='PNG')
        source.close()
        result, binding = fit_png(output.getvalue())
        self.assertLessEqual(binding['transmitted_patches'], MAX_PATCHES)
        with Image.open(io.BytesIO(result)) as image:
            self.assertEqual(image.mode, 'RGBA')
            self.assertEqual(image.getpixel((10, 10)), (255, 0, 0, 255))
            self.assertEqual(image.getpixel((image.width - 10, image.height - 10)), (0, 0, 255, 255))
            self.assertEqual(image.getpixel((image.width // 2, image.height // 2))[3], 0)

    def test_strip_boundaries_match_whole_canvas_filter(self):
        source = Image.new('RGBA', (160, 900), (10, 20, 30, 0))
        for y in range(0, 900, 17):
            source.paste((y % 255, 90, 170, 160), (0, y, 160, min(900, y + 9)))
        expected = source.resize((120, 675), Image.Resampling.LANCZOS)
        actual = resize_canvas_strips(source, (120, 675))
        # Compare visible, premultiplied color; straight RGB at alpha near zero
        # can differ by several integers after an equivalent rounding step.
        difference = ImageChops.difference(actual.convert('RGBa'), expected.convert('RGBa'))
        self.assertTrue(all(maximum <= 1 for minimum, maximum in difference.getextrema()))
        source.close();expected.close();actual.close();difference.close()


if __name__ == '__main__':
    unittest.main()
