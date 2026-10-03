import unittest

from wifivis.model import MAX_SOURCES, Scene


class SceneTests(unittest.TestCase):
    def test_add_select_drag_and_remove(self):
        scene = Scene()
        source = scene.add(.3, .6)
        self.assertEqual(scene.selected, source.id)
        self.assertEqual(scene.hit_test(.3, .6, 400, 900), source.id)
        scene.move(source.id, -.3, 1.5)
        self.assertEqual((source.x, source.y), (.015, .985))
        self.assertTrue(scene.remove_selected())
        self.assertFalse(scene.remove_selected())
        self.assertEqual(len(scene.sources), 1)

    def test_limit_and_unique_ids(self):
        scene = Scene()
        for _ in range(MAX_SOURCES):
            scene.add()
        self.assertEqual(len(scene.sources), MAX_SOURCES)
        self.assertIsNone(scene.add())
        old = scene.selected
        scene.remove_selected()
        self.assertGreater(scene.add().id, old)


if __name__ == "__main__":
    unittest.main()
