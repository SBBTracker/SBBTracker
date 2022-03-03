from PySide6.QtWidgets import QLabel, QMainWindow, QVBoxLayout, QWidget


class ShopDisplay(QMainWindow):
    def __init__(self):
        super().__init__()
        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)
        self.labels = [QLabel(f"Slot {i}", self) for i in range(0, 7)]
        for label in self.labels:
            layout.addWidget(label)
        self.setCentralWidget(main_widget)

    def update_card(self, state):
        if state.zone == "Shop":
            slot = state.slot
            template_id = state.content_id
            self.labels[int(slot)].setText(str(template_id))

    def clear(self):
        for ind, label in enumerate(self.labels):
            label.setText(f"Slot {ind}")