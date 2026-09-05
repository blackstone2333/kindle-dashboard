from app import DashboardState


if __name__ == "__main__":
    state = DashboardState("public", "fixtures/demo.json")
    print("generated", len(state.manifest["pages"]), "pages")
    for page in state.manifest["pages"]:
        print(page["id"], page["width"], page["height"], page["grayscale_levels"], page["sha256"])
