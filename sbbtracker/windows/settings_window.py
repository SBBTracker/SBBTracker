import re

import PySide6
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QIcon, QIntValidator, Qt
from PySide6.QtWidgets import QCheckBox, QComboBox, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow, \
    QMessageBox, QProgressDialog, QPushButton, QScrollArea, \
    QSlider, \
    QTabWidget, \
    QVBoxLayout, \
    QWidget

from sbbtracker import graphs, languages, settings, stats, version
from sbbtracker.languages import tr
from sbbtracker.utils import asset_utils
from sbbtracker.windows.constants import primary_color


class ImportThread(QThread):
    update_progress = Signal(int, int)

    def __init__(self, player_stats: stats.PlayerStats):
        super(ImportThread, self).__init__()
        self.player_stats = player_stats

    def run(self):
        self.player_stats.import_matches(self.update_progress.emit)


class NoScrollSlider(QSlider):
    def __init__(self, *args):
        super().__init__(*args)

    def wheelEvent(self, e:PySide6.QtGui.QWheelEvent):
        pass


class SliderCombo(QWidget):
    def __init__(self, minimum, maximum, default, step=1):
        super().__init__()
        slider_editor = QHBoxLayout(self)
        self.slider = NoScrollSlider(Qt.Horizontal)
        self.editor = QLineEdit()
        self.slider.setMaximum(maximum)
        self.slider.setMinimum(minimum)
        self.slider.setValue(default)
        self.slider.setSingleStep(step)
        self.slider.setTickInterval(step)
        self.slider.setMinimumWidth(100)
        self.slider.valueChanged.connect(lambda val: self.editor.setText(str(val)))
        self.editor.setValidator(QIntValidator(0, maximum))
        self.editor.setText(str(default))
        self.editor.textEdited.connect(
            lambda text: self.slider.setValue(int(text)) if text != '' else None)
        self.editor.setMinimumWidth(100)
        slider_editor.addWidget(self.slider)
        slider_editor.addWidget(self.editor)

    def get_value(self):
        return int(self.editor.text()) if self.editor.text() else 0


class HexColorEdit(QWidget):
    def __init__(self, default):
        super().__init__()
        layout = QHBoxLayout(self)
        self.editor = QLineEdit()
        color_box = QWidget()
        color_box.setMinimumSize(40, 40)
        layout.addWidget(self.editor)
        layout.addWidget(color_box)

        self.editor.textEdited.connect(lambda text: self.update_color(text, color_box))
        self.editor.setText(default)

    def update_color(self, text: str, widget: QWidget):
        valid_hex_color = re.search(r'^#(?:[0-9a-fA-F]{3}){1,2}$', text)

        if valid_hex_color:
            widget.setStyleSheet(f"background-color: {text} ;")


class SettingsCheckbox(QCheckBox):
    def __init__(self, setting: settings.Setting):
        super().__init__()
        self.setChecked(settings.get(setting))
        self.stateChanged.connect(lambda: settings.toggle(setting))


class SettingSection(QFrame):
    def __init__(self, title: str):
        super().__init__()
        internal_layout = QVBoxLayout(self)
        internal_layout.addWidget(QLabel(title), alignment=Qt.AlignTop | Qt.AlignHCenter)
        self.layout = QFormLayout(self)
        internal_layout.addLayout(self.layout)
        self.setObjectName("SettingSection")
        self.setStyleSheet("#SettingSection { border: 2px solid white; }")

    def addRow(self, *args):
        self.layout.addRow(*args)


class SettingsWindow(QMainWindow):
    def __init__(self, main_window):
        super().__init__()
        self.hide()
        self.setWindowModality(Qt.ApplicationModal)
        self.main_window = main_window
        main_widget = QFrame()
        main_layout = QVBoxLayout(main_widget)
        general_settings = QWidget()
        overlay_settings = QWidget()
        overlay_settings_scroll = QScrollArea(widgetResizable=True)
        overlay_settings_scroll.setWidget(overlay_settings)
        about_tab = QWidget()
        data_tab = QWidget()
        advanced_tab = QWidget()
        streaming_tab = QWidget()
        settings_tabs = QTabWidget()
        settings_tabs.addTab(general_settings, tr("General"))
        settings_tabs.addTab(data_tab, tr("Data"))
        settings_tabs.addTab(overlay_settings_scroll, tr("Overlay"))
        settings_tabs.addTab(advanced_tab, tr("Advanced"))
        settings_tabs.addTab(streaming_tab, tr("Streaming"))
        settings_tabs.addTab(about_tab, tr("About"))

        self.setWindowIcon(QIcon(asset_utils.get_asset("icon.png")))
        self.setWindowTitle("SBBTracker settings")

        about_layout = QVBoxLayout(about_tab)
        about_layout.addWidget(QLabel(f"""SBBTracker v{version.__version__}


SBBBattleSim by:
reggles44
isik
fredyybob


Special thanks to:
NoLucksGiven,
Asado,
HamiO,
chickenArise,
bnor,
and Lunco
"""))
        about_layout.addStretch()

        general_layout = QFormLayout(general_settings)

        language_select = QComboBox()
        language_select.addItems(languages.available_languages.keys())
        current_lang = {v: k for k, v in languages.available_languages.items()}[settings.get(settings.language)]
        lang_index = language_select.findText(current_lang)
        language_select.setCurrentIndex(lang_index if lang_index != -1 else 0)
        language_select.activated.connect(lambda _: settings.set_(settings.language,
                                                                  languages.available_languages[language_select.currentText()]))

        save_stats_checkbox = SettingsCheckbox(settings.save_stats)

        self.graph_color_chooser = QComboBox()
        palettes = list(graphs.color_palettes.keys())
        self.graph_color_chooser.addItems(palettes)
        self.graph_color_chooser.setCurrentIndex(palettes.index(settings.get(settings.live_palette)))
        self.graph_color_chooser.currentTextChanged.connect(main_window.live_graphs.set_color_palette)

        matchmaking_only_checkbox = SettingsCheckbox(settings.matchmaking_only)
        matchmaking_only_checkbox.setEnabled(bool(save_stats_checkbox.checkState()))

        save_stats_checkbox.stateChanged.connect(lambda state: matchmaking_only_checkbox.setEnabled(bool(state)))

        general_layout.addRow(tr("Language"), language_select)
        general_layout.addRow(tr("Save match results"), save_stats_checkbox)
        general_layout.addRow(tr("Ignore practice and group lobbies"), matchmaking_only_checkbox)
        general_layout.addRow(tr("Graph color palette"), self.graph_color_chooser)

        data_layout = QFormLayout(data_tab)
        export_button = QPushButton(tr("Export Stats"))
        export_button.clicked.connect(main_window.export_csv)
        delete_button = QPushButton(tr("Delete Stats"))
        delete_button.clicked.connect(lambda: main_window.delete_stats(self))
        self.last_backed_up = QLabel(tr("Last backup date") + f":{stats.most_recent_backup_date()}")
        backup_button = QPushButton(tr("Backup Stats"))
        backup_button.clicked.connect(self.backup)
        reimport_button = QPushButton(tr("Reimport Stats"))
        reimport_button.setDisabled(True)
        reimport_button.clicked.connect(self.import_stats)

        enable_upload = SettingsCheckbox(settings.upload_data)

        data_layout.addRow(self.last_backed_up, backup_button)
        data_layout.addWidget(export_button)
        data_layout.addWidget(delete_button)
        data_layout.addWidget(QLabel(tr("Reimporting is temporarily disabled")))
        data_layout.addWidget(reimport_button)
        data_layout.addRow(tr("Upload matches to sbbtracker.com"), enable_upload)
        data_layout.addWidget(QLabel(tr("Match uploads include your steam name, sbb id, board comps,placement, and change in mmr.")))

        overlay_layout = QVBoxLayout(overlay_settings)

        # General Overlay
        general_overlay_section = SettingSection(tr("General"))

        hide_overlay_in_bg_checkbox = SettingsCheckbox(settings.hide_overlay_in_bg)

        enable_overlay_checkbox = SettingsCheckbox(settings.enable_overlay)
        enable_overlay_checkbox.stateChanged.connect(lambda state: hide_overlay_in_bg_checkbox.setEnabled(bool(state)))

        show_tracker_button_checkbox = SettingsCheckbox(settings.show_tracker_button)
        show_tracker_button_checkbox.setEnabled(enable_overlay_checkbox.checkState())
        enable_overlay_checkbox.stateChanged.connect(lambda state: show_tracker_button_checkbox.setEnabled(bool(state)))

        show_hero_stats_checkbox = SettingsCheckbox(settings.enable_hero_stats)
        show_hero_stats_checkbox.setEnabled(enable_overlay_checkbox.checkState())
        enable_overlay_checkbox.stateChanged.connect(lambda state: show_hero_stats_checkbox.setEnabled(bool(state)))

        windows_scaling = SettingsCheckbox(settings.disable_scaling)
        windows_scaling.setEnabled(enable_overlay_checkbox.checkState())
        enable_overlay_checkbox.stateChanged.connect(lambda state: windows_scaling.setEnabled(bool(state)))

        general_overlay_section.addRow(tr("Enable overlay"), enable_overlay_checkbox)
        general_overlay_section.addRow(tr("Hide if SBB in background (restart to take effect)"), hide_overlay_in_bg_checkbox)
        general_overlay_section.addRow(tr("Enable 'Show Tracker' button"), show_tracker_button_checkbox)
        general_overlay_section.addRow(tr("Enable Hero Selection overlay"), show_hero_stats_checkbox)
        general_overlay_section.addRow(tr("Ignore windows scaling (Windows 8 compatability)"), windows_scaling)
        overlay_layout.addWidget(general_overlay_section)
        # Simulator
        simulator_section = SettingSection(tr("Simulator"))
        enable_sim_checkbox = SettingsCheckbox(settings.enable_sim)
        enable_sim_checkbox.setEnabled(enable_overlay_checkbox.checkState())
        enable_overlay_checkbox.stateChanged.connect(lambda state: enable_sim_checkbox.setEnabled(bool(state)))

        self.num_sims_silder = SliderCombo(100, 10000, settings.get(settings.number_simulations, 1000))
        self.num_threads_slider = SliderCombo(1, 4, settings.get(settings.number_threads))
        self.simulator_transparency_slider = SliderCombo(0, 100, settings.get(settings.simulator_transparency))
        self.simulator_scale_slider = SliderCombo(80, 120, settings.get(settings.simulator_scale))
        enable_comps = SettingsCheckbox(settings.enable_comps)
        enable_comps.setEnabled(enable_overlay_checkbox.checkState())

        simulator_section.addRow(tr("Enable simulator"), enable_sim_checkbox)
        simulator_section.addRow(tr("Number of simulations"), self.num_sims_silder)
        simulator_section.addRow(tr("Number of threads"), self.num_threads_slider)
        simulator_section.addRow(QLabel(tr("More threads = faster simulation but takes more computing power")))
        simulator_section.addRow(tr("Adjust simulator transparency"), self.simulator_transparency_slider)
        simulator_section.addRow(tr("Simulator scale"), self.simulator_scale_slider)
        overlay_layout.addWidget(simulator_section)
        # Comps
        comps_section = SettingSection(tr("Board Comps"))
        enable_overlay_checkbox.stateChanged.connect(lambda state: enable_comps.setEnabled(bool(state)))
        self.comp_transparency_slider = SliderCombo(0, 100, settings.get(settings.boardcomp_transparency))
        self.overlay_comps_scaling = SliderCombo(50, 200, settings.get(settings.overlay_comps_scaling))
        comps_section.addRow(tr("Enable board comps"), enable_comps)
        comps_section.addRow(tr("Board comps scaling"), self.overlay_comps_scaling)
        comps_section.addRow(tr("Adjust comps transparency"), self.comp_transparency_slider)
        overlay_layout.addWidget(comps_section)
        # Turn Display
        turn_section = SettingSection(tr("Turn Display"))
        enable_turn_display = SettingsCheckbox(settings.enable_turn_display)
        enable_turn_display.setEnabled(enable_overlay_checkbox.checkState())
        enable_overlay_checkbox.stateChanged.connect(lambda state: enable_turn_display.setEnabled(bool(state)))

        turn_display_font = QLineEdit()
        turn_display_font.setValidator(QIntValidator(1, 100))
        turn_display_font.setText(str(settings.get(settings.turn_display_font_size)))
        turn_display_font.textChanged.connect(
            lambda text: settings.set_(settings.turn_display_font_size, text) if text != '' else None)

        self.turn_transparency = SliderCombo(0, 100, settings.get(settings.turn_display_transparency))
        turn_section.addRow(tr("Enable turn display"), enable_turn_display)
        turn_section.addRow(tr("Turn font size (restart to resize)"), turn_display_font)
        turn_section.addRow(tr("Turn transparency"), self.turn_transparency)
        overlay_layout.addWidget(turn_section)

        advanced_layout = QFormLayout(advanced_tab)
        enable_export_comp_checkbox = SettingsCheckbox(settings.export_comp_button)
        show_id_mode = SettingsCheckbox(settings.show_ids)
        show_id_window = SettingsCheckbox(settings.show_id_window)
        advanced_layout.addRow(tr("Enable export last comp button"), enable_export_comp_checkbox)
        advanced_layout.addRow(tr("Hide art and show template ids"), show_id_mode)
        advanced_layout.addRow(tr("Enable ID window"), show_id_window)

        streaming_layout = QFormLayout(streaming_tab)
        enable_stream_overlay = QCheckBox()
        enable_stream_overlay.setChecked(settings.get(settings.streaming_mode))
        enable_stream_overlay.stateChanged.connect(lambda: settings.toggle(settings.streaming_mode))

        self.stream_overlay_color = HexColorEdit(settings.get(settings.stream_overlay_color))

        streamable_score = QCheckBox()
        streamable_score.setChecked(settings.get(settings.streamable_score_list))
        streamable_score.stateChanged.connect(lambda: settings.toggle(settings.streamable_score_list))

        self.max_scores = QLineEdit()
        self.max_scores.setText(str(settings.get(settings.streamable_score_max_len)))
        self.max_scores.setValidator(QIntValidator(1, 50))

        reset_scores = QPushButton(tr("Reset"))
        reset_scores.clicked.connect(main_window.streamable_scores.reset)

        streaming_layout.addRow(tr("Show capturable score window"), streamable_score)
        streaming_layout.addRow(tr("Number of scores per line"), self.max_scores)
        streaming_layout.addRow(tr("Reset scores"), reset_scores)
        streaming_layout.addRow(QLabel(tr("Chroma-key filter #00FFFF to hide the scores background")))
        streaming_layout.addRow(QLabel(""))
        streaming_layout.addRow(tr("Show capturable overlay window"), enable_stream_overlay)
        streaming_layout.addRow(tr("Background color"), self.stream_overlay_color)
        streaming_layout.addRow(QLabel(tr("Enabling this will add a copy of the overlay behind your other windows.")))
        streaming_wiki_link = QLabel(
            "<a href=\"https://github.com/SBBTracker/SBBTracker/wiki/Streaming-Settings-Guide\" style=\"color: "
            f"{primary_color};\">{tr('Wiki guide here')}</a>")
        streaming_wiki_link.setTextFormat(Qt.RichText)
        streaming_wiki_link.setTextInteractionFlags(Qt.TextBrowserInteraction)
        streaming_wiki_link.setOpenExternalLinks(True)
        streaming_layout.addRow(streaming_wiki_link)

        save_close_layout = QHBoxLayout()
        self.save_button = QPushButton(tr("Save"))
        self.save_button.clicked.connect(self.save)
        close_button = QPushButton(tr("Cancel"))
        close_button.clicked.connect(self.hide)
        save_close_layout.addStretch()
        save_close_layout.addWidget(self.save_button)
        save_close_layout.addWidget(close_button)

        main_layout.addWidget(settings_tabs)
        main_layout.addLayout(save_close_layout)

        self.setCentralWidget(main_widget)
        self.setMinimumSize(600, 600)

    def save(self):
        settings.set_(settings.live_palette, self.graph_color_chooser.currentText())
        settings.set_(settings.boardcomp_transparency, self.comp_transparency_slider.get_value())
        settings.set_(settings.simulator_transparency, self.simulator_transparency_slider.get_value())
        settings.set_(settings.simulator_scale, max(self.simulator_scale_slider.get_value(), 80))
        settings.set_(settings.number_threads, max(self.num_threads_slider.get_value(), 4))
        settings.set_(settings.number_simulations, self.num_sims_silder.get_value())
        settings.set_(settings.stream_overlay_color, self.stream_overlay_color.editor.text())
        settings.set_(settings.overlay_comps_scaling, self.overlay_comps_scaling.get_value())
        settings.set_(settings.turn_display_transparency, self.turn_transparency.get_value())

        max_scores_val = self.max_scores.text()
        if max_scores_val and int(max_scores_val) > 0:
            settings.set_(settings.streamable_score_max_len, int(max_scores_val))

        settings.save()
        self.hide()

        self.main_window.shop_display.show() if settings.get(settings.show_id_window) else self.main_window.shop_display.hide()
        self.main_window.overlay.update_comp_scaling()
        self.main_window.streamer_overlay.update_comp_scaling()
        self.main_window.overlay.set_transparency()
        self.main_window.show_scores()
        if not settings.get(settings.hide_overlay_in_bg) or self.main_window.overlay.visible:
            self.main_window.show_overlay()
        if settings.get(settings.streaming_mode):
            self.main_window.streamer_overlay.show()
            self.main_window.streamer_overlay.centralWidget().setStyleSheet(
                f"QWidget#overlay {{background-color: {settings.get(settings.stream_overlay_color)}}}")
            self.main_window.streamer_overlay.turn_display.setVisible(settings.get(settings.enable_turn_display))
        else:
            self.main_window.streamer_overlay.hide()
        self.main_window.overlay.set_comps_enabled(settings.get(settings.enable_comps))
        self.main_window.streamer_overlay.set_comps_enabled(settings.get(settings.enable_comps))
        self.main_window.overlay.simulation_stats.setVisible(settings.get(settings.enable_sim))
        self.main_window.overlay.show_button.setVisible(settings.get(settings.show_tracker_button))
        self.main_window.overlay.turn_display.setVisible(settings.get(settings.enable_turn_display))
        self.main_window.export_comp_action.setVisible(settings.get(settings.export_comp_button))

    def import_stats(self):
        message = tr("""
Would you like to import your old games? This is done by 
reading the record files generated by the game. This will 
import games going back to Dec 14 2021 (assuming you have not
deleted the record files).

Note that not all games are guaranteed to be imported.

If you have games already recorded from before Jan 2nd 2022
duplicated matches may appear. You may wish to backup and delete 
your current stats before doing this, or manually remove stats 
yourself.

The importer may take a long time to complete. Please be patient.



""")
        reply = QMessageBox.question(self, tr("Reimport Stats?"), message)
        if reply == QMessageBox.Yes:
            self.import_thread = ImportThread(self.main_window.player_stats)
            self.progress = QProgressDialog(tr("Import progress"), tr("Cancel"), 0, 100, self)
            self.progress.setWindowTitle(tr("Importer"))
            self.import_thread.update_progress.connect(self.handle_import_progress)
            self.import_thread.start()
            self.progress.canceled.connect(self.import_thread.terminate)
            self.progress.show()
            self.main_window.match_history.update_history_table()

    def backup(self):
        stats.backup_stats(force=True)
        self.last_backed_up.setText(tr("Last backup date") + f": {stats.most_recent_backup_date()}")

    def handle_import_progress(self, num, totalsize):
        import_percent = num * 100 / totalsize
        self.progress.setValue(import_percent)
        if num == totalsize:
            self.progress.close()
