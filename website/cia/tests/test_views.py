import json
import tempfile
from pathlib import Path

from django.test import SimpleTestCase, override_settings
from django.urls import reverse


TEST_TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [str(Path(__file__).parent / "templates")],
    "APP_DIRS": True,
}]


@override_settings(
    ROOT_URLCONF="cia.tests.urls",
    MIDDLEWARE=[],
    TEMPLATES=TEST_TEMPLATES,
)
class CIAViewsTests(SimpleTestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.override = override_settings(CIA_DATA_DIR=str(self.root))
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(self.temporary_directory.cleanup)
        self._create_pair(
            "CO2-He", "co2-he", "unique", "co2", "recommended",
            ["recommended", "other"],
        )
        self._create_pair(
            "CO2-Ar", "co2-ar", "unique", "co2", "sole", ["sole"],
        )
        self._create_pair(
            "H-He", "h-he", "no_unique_active_species", None, "neutral",
            ["neutral"],
        )

    def _write_json(self, path, value):
        path.write_text(json.dumps(value), encoding="utf-8")

    def _create_pair(
        self, formula, slug, status, active_species, recommended, dataset_ids
    ):
        directory = self.root / formula
        directory.mkdir()
        components = [
            {"formula": part.upper(), "slug": part.lower()}
            for part in formula.split("-")
        ]
        pair = {
            "formula": formula,
            "slug": slug,
            "active_species_status": status,
            "active_species": active_species,
            "components": components,
        }
        summaries = []
        for dataset_id in dataset_ids:
            metadata_file = "{}_{}.json".format(formula, dataset_id)
            cia_file = "{}_{}.cia".format(formula, dataset_id)
            cia_files = [cia_file]
            if dataset_id == "recommended":
                cia_files.extend(
                    "{}_{}_{}.cia".format(formula, dataset_id, number)
                    for number in range(2, 7)
                )
            summaries.append({
                "dataset_id": dataset_id,
                "dataset_version": "20260101",
                "metadata_file": metadata_file,
            })
            self._write_json(directory / metadata_file, {
                "collision_pair": pair,
                "dataset": {
                    "id": dataset_id,
                    "version": "20260101",
                    "repository": {"name": "Fixture repository"},
                    "collision_induced_absorption_xsecs": {
                        "min_temperature": 100,
                        "max_temperature": 200,
                        "min_wavenumber": 1,
                        "max_wavenumber": 2,
                        "units": {"temperature": "K"},
                        "files": [{
                            "filename": filename,
                            "temperature": 51.700,
                            "npoints": 2,
                            "wavenumber_resolution": 1,
                        } for filename in cia_files],
                    },
                    "sources": [
                        {
                            "authors": ["Fixture Author"],
                            "year": 2026,
                            "title": "Fixture article about CO2, CH4 and HITRAN2024",
                            "source_url": "https://example.com/article",
                        },
                        {
                            "authors": ["Second Author"],
                            "year": 2025,
                            "title": "Second fixture article",
                            "source_url": "https://example.com/second",
                        },
                        {
                            "citation_key": "hitran_cia_repository",
                            "authors": ["HITRAN CIA Team"],
                            "year": 2024,
                            "title": "HITRAN online data",
                            "source_url": "https://hitran.org/cia/",
                        },
                    ],
                },
            })
            for filename in cia_files:
                (directory / filename).write_text("1 2\n", encoding="ascii")
        self._write_json(directory / "{}.json".format(formula), {
            "collision_pair": pair,
            "version": "20260101",
            "recommended_dataset": recommended,
            "datasets": summaries,
        })

    def test_index_links_category_without_listing_its_pairs(self):
        response = self.client.get(reverse("cia:index"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("CO<sub>2</sub>", response.content.decode())
        self.assertContains(response, "Pairs without a unique active species")
        self.assertContains(response, 'class="well cia-index-group"', count=2)
        self.assertContains(response, "link-list-group-item cia-index-item")
        self.assertContains(response, "cia/cia.css")
        self.assertContains(
            response,
            reverse("cia:pairs_without_unique_active_species"),
        )
        self.assertNotContains(response, "H-He")

    def test_category_lists_pairs_with_links_to_pair_details(self):
        response = self.client.get(
            reverse("cia:pairs_without_unique_active_species")
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "H-He")
        self.assertContains(response, reverse("cia:pair", args=["h-he"]))
        self.assertNotContains(response, "CO<sub>2</sub>-He", html=True)
        self.assertContains(response, "well cia-list-panel")
        self.assertContains(response, "link-list-group-item cia-list-item")

    def test_species_lists_its_pairs(self):
        response = self.client.get(
            reverse("cia:species", args=["co2"])
        )
        self.assertContains(response, "CO<sub>2</sub>-He", html=True)
        self.assertContains(response, "well cia-list-panel")
        self.assertContains(response, "link-list-group-item cia-list-item")

    def test_pair_puts_recommended_before_other(self):
        response = self.client.get(
            reverse("cia:pair", args=["co2-he"])
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        body = content[content.index("<body>"):]
        self.assertLess(
            body.index("&larr; Collision pairs for CO<sub>2</sub>"),
            body.index(
                "<h1>Collision-induced absorption data sets for "
                "CO<sub>2</sub>-He</h1>"
            ),
        )
        self.assertContains(response, reverse("cia:species", args=["co2"]))
        self.assertContains(response, "well cia-dataset-panel", count=1)
        self.assertContains(response, "link-list-group-item cia-dataset-item")
        self.assertContains(response, "cia-dataset-item cia-recommended")
        self.assertLess(content.index("recommended"), content.index("other"))
        self.assertNotContains(response, "Recommended datasets")
        self.assertNotContains(response, "Other resources and data")
        self.assertNotContains(response, "Resources and data")

    def test_pair_omits_other_section_when_there_are_no_other_datasets(self):
        response = self.client.get(reverse("cia:pair", args=["co2-ar"]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Recommended datasets")
        self.assertNotContains(response, "Other resources and data")
        self.assertContains(response, "well cia-dataset-panel", count=1)

    def test_unassigned_pair_links_back_to_category(self):
        response = self.client.get(reverse("cia:pair", args=["h-he"]))
        body = response.content.decode()
        self.assertContains(
            response,
            reverse("cia:pairs_without_unique_active_species"),
        )
        self.assertLess(
            body.index("&larr; Pairs without a unique active species"),
            body.index(
                "<h1>Collision-induced absorption data sets for H-He</h1>"
            ),
        )

    def test_dataset_layout_metadata_sources_and_files(self):
        response = self.client.get(
            reverse("cia:dataset", args=["co2-he", "recommended"])
        )
        content = response.content.decode()
        body = content[content.index("<body>"):]
        self.assertIn(
            "<h1>Collision-induced absorption data for "
            "CO<sub>2</sub>-He</h1>",
            body,
        )
        self.assertNotIn("<h1>CO2-He: recommended</h1>", body)
        self.assertNotIn("<h2>recommended</h2>", body)
        self.assertLess(
            body.index("&larr; CO<sub>2</sub>-He datasets"),
            body.index("<h1>"),
        )
        self.assertLess(
            body.index("<h1>Collision-induced absorption data for "),
            body.index("<dt>Dataset ID</dt>"),
        )
        summary_fields = [
            "<dt>Dataset ID</dt>",
            "<dt>Version</dt>",
            "<dt>Repository</dt>",
            "<dt>Temperature range</dt>",
            "<dt>Wavenumber range</dt>",
        ]
        positions = [body.index(field) for field in summary_fields]
        self.assertEqual(positions, sorted(positions))
        self.assertContains(response, "Fixture repository")
        self.assertNotContains(response, "Link to article")
        self.assertContains(
            response,
            '[<a href="https://example.com/article">link to article</a>]',
        )
        self.assertContains(
            response,
            '[<a href="https://hitran.org/cia/">link to website</a>]',
        )
        self.assertContains(response, 'href="https://example.com/article"')
        self.assertIn(
            "Fixture article about CO<sub>2</sub>, CH<sub>4</sub> and HITRAN2024",
            body,
        )
        self.assertNotIn("HITRAN<sub>2024</sub>", body)
        self.assertContains(response, "CO2-He_recommended.cia")
        self.assertContains(response, "CO2-He_recommended.json")
        self.assertContains(
            response,
            "CO<sub>2</sub>-He_recommended.cia",
            html=True,
        )
        self.assertContains(
            response,
            "CO<sub>2</sub>-He_recommended.json",
            html=True,
        )
        self.assertNotContains(response, "Recommended dataset")
        self.assertContains(response, "<dt>Dataset ID</dt>", html=True)
        self.assertContains(response, "<dd>recommended</dd>", html=True)
        self.assertContains(response, "<h4>Metadata</h4>", html=True)
        self.assertContains(response, "well cia-metadata-panel")
        self.assertContains(response, "cia-metadata-summary")
        self.assertContains(response, "cia-metadata-file")
        self.assertContains(response, "well cia-data-panel")
        self.assertContains(response, "51.7K")
        self.assertNotContains(response, "51.700K")
        self.assertNotContains(response, "<th>Resolution</th>", html=True)
        self.assertContains(response, "<th>Files</th>", html=True)
        self.assertContains(response, "Show 6 files")
        self.assertContains(response, 'id="cia-files" hidden')
        self.assertContains(response, "Hide files")
        self.assertNotContains(response, "<h2>Sources</h2>", html=True)
        self.assertContains(response, "<h4>References</h4>", html=True)
        self.assertNotContains(response, "<h2>Files</h2>", html=True)
        self.assertIn("<ol>", body)
        self.assertLess(
            body.index("cia-data-panel"),
            body.index("<h4>References</h4>"),
        )

    def test_download_serves_only_listed_dataset_files(self):
        url = reverse(
            "cia:download",
            args=["co2-he", "recommended", "CO2-He_recommended.cia"],
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"1 2\n")
        self.assertEqual(response["Content-Type"], "text/plain")
        self.assertIn(
            'inline; filename="CO2-He_recommended.cia"',
            response["Content-Disposition"],
        )

        metadata_url = reverse(
            "cia:download",
            args=["co2-he", "recommended", "CO2-He_recommended.json"],
        )
        metadata_response = self.client.get(metadata_url)
        self.assertEqual(metadata_response.status_code, 200)
        self.assertEqual(metadata_response["Content-Type"], "application/json")
        self.assertIn(
            'inline; filename="CO2-He_recommended.json"',
            metadata_response["Content-Disposition"],
        )

        unlisted = self.root / "CO2-He" / "secret.cia"
        unlisted.write_text("secret", encoding="ascii")
        url = reverse(
            "cia:download",
            args=["co2-he", "recommended", "secret.cia"],
        )
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_invalid_resources_return_404(self):
        self.assertEqual(
            self.client.get(reverse("cia:species", args=["missing"])).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(reverse("cia:pair", args=["missing"])).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                reverse("cia:dataset", args=["co2-he", "missing"])
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                "/cia/pairs-without-unique-active-species/missing/"
            ).status_code,
            404,
        )

    def test_download_rejects_path_traversal(self):
        response = self.client.get(
            "/cia/pairs/co2-he/datasets/recommended/files/../secret.cia"
        )
        self.assertEqual(response.status_code, 404)
