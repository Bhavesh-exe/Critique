import reflex as rx
import reflex.constants as rx_constants

# Fix npm 11 / Node 24 strict EOVERRIDE conflict in Reflex 0.9.8
if hasattr(rx_constants, "PackageJson"):
    rx_constants.PackageJson.OVERRIDES = {}

config = rx.Config(
    app_name="critique_ui",
    plugins=[
        rx.plugins.RadixThemesPlugin(
            theme=rx.theme(
                appearance="dark",
                has_background=True,
                accent_color="ruby",
                gray_color="slate",
                radius="large",
            )
        ),
        rx.plugins.SitemapPlugin(),
    ],
)
