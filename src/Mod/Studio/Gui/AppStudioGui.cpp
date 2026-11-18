// SPDX-License-Identifier: LGPL-2.1-or-later
//
// StudioGui: Studio's C++ helpers for the shell, where FreeCAD offers no Python API, or where Python
// can't safely reach (see style_panels). See docs/adr/0007-lazy-loading-command-catalog.md.

#include <map>
#include <set>
#include <string>

#include <QAbstractSpinBox>
#include <QAction>
#include <QApplication>
#include <QBuffer>
#include <QComboBox>
#include <QIcon>
#include <QKeyEvent>
#include <QLabel>
#include <QLineEdit>
#include <QPainter>
#include <QPlainTextEdit>
#include <QStatusBar>
#include <QSvgRenderer>
#include <QTabWidget>
#include <QTextEdit>
#include <QToolButton>
#include <QTreeView>

#include <CXX/Extensions.hxx>

#include <Base/Exception.h>
#include <Base/Interpreter.h>
#include <Base/PyObjectBase.h>  // PyMOD_INIT_FUNC
#include <Base/Type.h>
#include <Gui/Application.h>
#include <Gui/BitmapFactory.h>
#include <Gui/Command.h>
#include <Gui/MainWindow.h>
#include <Gui/Workbench.h>
#include <Gui/WorkbenchManager.h>

namespace StudioGui
{

namespace
{
bool isTextInput(QWidget* widget)
{
    if (qobject_cast<QLineEdit*>(widget) || qobject_cast<QTextEdit*>(widget)
        || qobject_cast<QPlainTextEdit*>(widget) || qobject_cast<QAbstractSpinBox*>(widget)) {
        return true;
    }
    auto* combo = qobject_cast<QComboBox*>(widget);
    return combo && combo->isEditable();
}

// FreeCAD's panels as Studio styles them (docs/adr/0010, studio/shell/appearance.py).
const char* const PropertyEditorClass = "Gui::PropertyEditor::PropertyEditor";
const char* const OriginalIcon = "studioOriginalIcon";

QList<QTreeView*> propertyEditors(QWidget* main)
{
    QList<QTreeView*> editors;
    for (auto* view : main->findChildren<QTreeView*>()) {
        if (view->inherits(PropertyEditorClass)) {
            editors.append(view);
        }
    }
    return editors;
}

/// The actions behind the float, overlay and close buttons in panel title bars. FreeCAD's panel
/// manager owns them; one action serves every panel.
std::set<QAction*> titleActions(QWidget* main)
{
    static const QStringList names {
        QStringLiteral("OBTN Float"),
        QStringLiteral("OBTN Overlay"),
        QStringLiteral("OBTN Close"),
    };
    std::set<QAction*> actions;
    for (auto* button : main->findChildren<QToolButton*>()) {
        QAction* action = button->defaultAction();
        if (action && names.contains(action->data().toString())) {
            actions.insert(action);
        }
    }
    return actions;
}

QIcon tinted(const QIcon& icon, const QColor& color)
{
    QPixmap pixmap = icon.pixmap(32, 32);
    if (pixmap.isNull()) {
        return icon;
    }
    QPainter painter(&pixmap);
    painter.setCompositionMode(QPainter::CompositionMode_SourceIn);
    painter.fillRect(pixmap.rect(), color);
    painter.end();
    return QIcon(pixmap);
}

/// An SVG drawn at `size` logical pixels for the screen's scale. Qt's renderer directly: FreeCAD's
/// pixmapFromSvg costs ~0.45 ms a drawing at startup (file checks, string round trips, log blocking).
QPixmap drawing(const QString& path, int size)
{
    QSvgRenderer renderer(path);
    if (!renderer.isValid()) {
        return {};
    }
    const qreal scale = qApp->devicePixelRatio();
    QImage image(QSize(size, size) * scale, QImage::Format_ARGB32_Premultiplied);
    image.fill(Qt::transparent);
    QPainter painter(&image);
    renderer.render(&painter);
    painter.end();
    QPixmap pixmap = QPixmap::fromImage(image);
    pixmap.setDevicePixelRatio(scale);
    return pixmap;
}

Py::String colorName(const QColor& color)
{
    return Py::String(color.name().toUpper().toStdString());
}
}  // namespace

/// Application-wide event filter for Studio's keyboard shortcuts (docs/adr/0008). Every event of
/// the app passes through it, so it stays in C++: only key events for widgets of the main window
/// that aren't text fields, with no modal dialog open, reach the Python callback
/// callback(event_type, key, modifiers) -> bool "claimed". A claimed ShortcutOverride is accepted,
/// so Qt doesn't treat the key as a shortcut and the key press comes next.
class KeyEventGate: public QObject
{
public:
    explicit KeyEventGate(const Py::Object& callback)
        : callback(callback)
    {}

    bool eventFilter(QObject* watched, QEvent* event) override
    {
        const QEvent::Type type = event->type();
        if ((type != QEvent::ShortcutOverride && type != QEvent::KeyPress) || !watched->isWidgetType()) {
            return false;
        }
        auto* widget = static_cast<QWidget*>(watched);
        if (isTextInput(widget) || QApplication::activeModalWidget()
            || widget->window() != Gui::getMainWindow()) {
            return false;
        }
        auto* keyEvent = static_cast<QKeyEvent*>(event);
        Base::PyGILStateLocker lock;
        try {
            Py::Tuple args(3);
            args.setItem(0, Py::Long(static_cast<long>(type)));
            args.setItem(1, Py::Long(static_cast<long>(keyEvent->key())));
            args.setItem(2, Py::Long(static_cast<long>(keyEvent->modifiers().toInt())));
            const bool claimed = Py::Callable(callback).apply(args).isTrue();
            if (claimed && type == QEvent::ShortcutOverride) {
                event->accept();
            }
            return claimed;
        }
        catch (Py::Exception&) {
            Base::PyException error;  // takes the pending Python error
            error.reportException();
            return false;
        }
    }

private:
    Py::Object callback;
};

class Module: public Py::ExtensionModule<Module>
{
public:
    Module()
        : Py::ExtensionModule<Module>("StudioGui")
    {
        add_varargs_method(
            "initialize_workbench",
            &Module::initializeWorkbench,
            "initialize_workbench(name) -> bool\n\n"
            "Makes a workbench's commands exist without switching to it: does what FreeCAD's\n"
            "first activation does before activating (Gui::Application::activateWorkbench).\n"
            "For a Python workbench it creates the C++ workbench object and attaches it as\n"
            "__Workbench__ (Initialize() needs it); then it runs Initialize(); for a C++ workbench\n"
            "it then creates the workbench object. A later activateWorkbench() sees __Workbench__\n"
            "and skips both, so nothing runs twice. Returns False if the workbench was already\n"
            "initialized."
        );
        add_varargs_method(
            "add_key_filter",
            &Module::addKeyFilter,
            "add_key_filter(callback) -> int\n\n"
            "Installs an application-wide key filter (docs/adr/0008). callback(event_type, key,\n"
            "modifiers) -> bool is called only for ShortcutOverride and KeyPress events of main-window\n"
            "widgets that aren't text fields, while no modal dialog is open; True claims the key.\n"
            "Returns an id for remove_key_filter()."
        );
        add_varargs_method(
            "remove_key_filter",
            &Module::removeKeyFilter,
            "remove_key_filter(id): removes a filter installed by add_key_filter()."
        );
        add_varargs_method(
            "declared_shortcut",
            &Module::declaredShortcut,
            "declared_shortcut(name) -> str\n\n"
            "The key sequence a command declares as its default (Command::getAccel), whether or not\n"
            "a menu or toolbar shows the command; '' if it declares none. FreeCAD's own Python API\n"
            "reports a command's shortcut only through its button. KeyError for an unknown command."
        );
        add_varargs_method(
            "add_icons",
            &Module::addIcons,
            "add_icons({svg_path: [icon names]}) -> int\n\n"
            "Puts each drawing into FreeCAD's icon cache under each of the names, replacing what is\n"
            "cached (docs/adr/0010): FreeCAD's commands, menus and model tree look icons up there by\n"
            "name first. Each SVG is drawn once, at 32 px (times the screen scale). Returns the number of drawings added."
        );
        add_varargs_method(
            "style_panels",
            &Module::stylePanels,
            "style_panels(group_background, group_text, icon_color, status_text)\n\n"
            "Styles FreeCAD's panels where Qt's palette doesn't reach (docs/adr/0010): the property\n"
            "editors' group rows, their tab box drawn flat, the panel title buttons' icons tinted, the\n"
            "status bar's text color (set again, which re-polishes its labels after a mode switch).\n"
            "Colors are '#RRGGBB'. In C++ because Python wrappers of some of these widgets (FreeCAD's\n"
            "model tree, its panel manager's) make FreeCAD abort when it exits (docs/BASELINE.md)."
        );
        add_varargs_method(
            "panel_style",
            &Module::panelStyle,
            "panel_style() -> dict\n\n"
            "What style_panels set, read back for checks: 'group_rows' [(background, text)] per\n"
            "property editor, 'flat_property_area' [bool], 'title_icons' {action name: PNG bytes},\n"
            "'status_labels' [(name, text color)] for the status bar's plain labels, 'views'\n"
            "[(class name, paints its background)] for the model trees and property editors.\n"
            "Colors '#RRGGBB'."
        );
        add_varargs_method(
            "units_changed",
            &Module::unitsChanged,
            "units_changed()\n\n"
            "Shows sizes in the unit schema just set (PLAN 3.1), as FreeCAD's own unit menu in the status\n"
            "bar does: updates the documents' views and repaints the property editors, whose rows format\n"
            "their sizes when drawn. In C++ for the same reason as style_panels."
        );
        initialize("Studio's C++ helpers for the shell (docs/adr/0007, 0008, 0010).");
    }

private:
    std::map<long, KeyEventGate*> gates;
    long nextGateId = 1;

    Py::Object addKeyFilter(const Py::Tuple& args)
    {
        PyObject* callback = nullptr;
        if (!PyArg_ParseTuple(args.ptr(), "O", &callback)) {
            throw Py::Exception();
        }
        if (!PyCallable_Check(callback)) {
            throw Py::TypeError("add_key_filter() needs a callable");
        }
        auto* gate = new KeyEventGate(Py::Object(callback));
        qApp->installEventFilter(gate);
        const long id = nextGateId++;
        gates[id] = gate;
        return Py::Long(id);
    }

    Py::Object declaredShortcut(const Py::Tuple& args)
    {
        char* name = nullptr;
        if (!PyArg_ParseTuple(args.ptr(), "s", &name)) {
            throw Py::Exception();
        }
        Gui::Command* command = Gui::Application::Instance->commandManager().getCommandByName(name);
        if (!command) {
            throw Py::KeyError(name);
        }
        const char* accel = command->getAccel();
        return Py::String(accel ? accel : "");
    }

    Py::Object removeKeyFilter(const Py::Tuple& args)
    {
        long id = 0;
        if (!PyArg_ParseTuple(args.ptr(), "l", &id)) {
            throw Py::Exception();
        }
        auto found = gates.find(id);
        if (found != gates.end()) {
            qApp->removeEventFilter(found->second);
            delete found->second;
            gates.erase(found);
        }
        return Py::None();
    }

    Py::Object addIcons(const Py::Tuple& args)
    {
        PyObject* mapping = nullptr;
        if (!PyArg_ParseTuple(args.ptr(), "O!", &PyDict_Type, &mapping)) {
            throw Py::Exception();
        }
        Py::Dict drawings(mapping);
        Py::List paths = drawings.keys();
        long added = 0;
        for (Py::List::size_type i = 0; i < paths.length(); ++i) {
            const std::string path = Py::String(paths[i]).as_std_string("utf-8");
            const QPixmap pixmap = drawing(QString::fromStdString(path), 32);
            if (pixmap.isNull()) {
                throw Py::ValueError("not a drawing: " + path);
            }
            Py::Sequence names(drawings.getItem(paths[i]));
            for (Py::Sequence::size_type j = 0; j < names.length(); ++j) {
                const std::string name = Py::String(names[j]).as_std_string("utf-8");
                Gui::BitmapFactory().addPixmapToCache(name.c_str(), pixmap);
            }
            ++added;
        }
        return Py::Long(added);
    }

    Py::Object stylePanels(const Py::Tuple& args)
    {
        char* groupBackground = nullptr;
        char* groupText = nullptr;
        char* iconColor = nullptr;
        char* statusText = nullptr;
        if (!PyArg_ParseTuple(args.ptr(), "ssss", &groupBackground, &groupText, &iconColor, &statusText)) {
            throw Py::Exception();
        }
        Gui::MainWindow* main = Gui::getMainWindow();
        if (!main) {
            return Py::None();
        }
        for (auto* editor : propertyEditors(main)) {
            editor->setProperty("groupBackground", QBrush(QColor(QString::fromUtf8(groupBackground))));
            editor->setProperty("groupTextColor", QColor(QString::fromUtf8(groupText)));
            editor->viewport()->update();
        }
        for (auto* tabs : main->findChildren<QTabWidget*>(QStringLiteral("propertyTab"))) {
            tabs->setDocumentMode(true);  // no frame: the area matches the model tree above it
        }
        const QColor ink(QString::fromUtf8(iconColor));
        for (QAction* action : titleActions(main)) {
            if (!action->property(OriginalIcon).isValid()) {  // tint FreeCAD's icon, not a tinted copy
                action->setProperty(OriginalIcon, QVariant::fromValue(action->icon()));
            }
            action->setIcon(tinted(action->property(OriginalIcon).value<QIcon>(), ink));
        }
        // FreeCAD's own normal-message style (Gui::StatusBarObserver), with the new color.
        main->statusBar()->setStyleSheet(
            QStringLiteral("#statusBar{color: %1}").arg(QString::fromUtf8(statusText))
        );
        return Py::None();
    }

    Py::Object panelStyle(const Py::Tuple& args)
    {
        if (!PyArg_ParseTuple(args.ptr(), "")) {
            throw Py::Exception();
        }
        Py::Dict result;
        Gui::MainWindow* main = Gui::getMainWindow();
        if (!main) {
            return result;
        }
        Py::List rows;
        for (auto* editor : propertyEditors(main)) {
            Py::Tuple row(2);
            row.setItem(0, colorName(editor->property("groupBackground").value<QBrush>().color()));
            row.setItem(1, colorName(editor->property("groupTextColor").value<QColor>()));
            rows.append(row);
        }
        result.setItem("group_rows", rows);
        Py::List flat;
        for (auto* tabs : main->findChildren<QTabWidget*>(QStringLiteral("propertyTab"))) {
            flat.append(Py::Boolean(tabs->documentMode()));
        }
        result.setItem("flat_property_area", flat);
        Py::Dict icons;
        for (QAction* action : titleActions(main)) {
            QByteArray png;
            QBuffer buffer(&png);
            buffer.open(QIODevice::WriteOnly);
            action->icon().pixmap(32, 32).save(&buffer, "PNG");
            icons.setItem(
                action->data().toString().toStdString(),
                Py::Object(PyBytes_FromStringAndSize(png.constData(), png.size()), true)
            );
        }
        result.setItem("title_icons", icons);
        Py::List labels;
        for (auto* label : main->statusBar()->findChildren<QLabel*>()) {
            if (label->objectName() == QLatin1String("StudioHint") || !label->styleSheet().isEmpty()) {
                continue;
            }
            Py::Tuple entry(2);
            const QString name = label->objectName().isEmpty() ? label->text() : label->objectName();
            entry.setItem(0, Py::String(name.toStdString()));
            entry.setItem(1, colorName(label->palette().color(label->foregroundRole())));
            labels.append(entry);
        }
        result.setItem("status_labels", labels);
        Py::List views;
        for (auto* view : main->findChildren<QAbstractItemView*>()) {
            if (view->inherits("Gui::TreeWidget") || view->inherits("Gui::PropertyEditor::PropertyEditor")) {
                Py::Tuple entry(2);
                entry.setItem(0, Py::String(view->metaObject()->className()));
                entry.setItem(1, Py::Boolean(view->viewport()->autoFillBackground()));
                views.append(entry);
            }
        }
        result.setItem("views", views);
        return result;
    }

    Py::Object unitsChanged(const Py::Tuple& args)
    {
        if (!PyArg_ParseTuple(args.ptr(), "")) {
            throw Py::Exception();
        }
        Gui::Application::Instance->onUpdate();
        if (Gui::MainWindow* main = Gui::getMainWindow()) {
            for (auto* editor : propertyEditors(main)) {
                editor->viewport()->update();
            }
        }
        return Py::None();
    }

    Py::Object initializeWorkbench(const Py::Tuple& args)
    {
        char* name = nullptr;
        if (!PyArg_ParseTuple(args.ptr(), "s", &name)) {
            throw Py::Exception();
        }

        // The Python workbench handler, as FreeCAD keeps it (KeyError if unknown).
        Py::Module gui(PyImport_ImportModule("FreeCADGui"), true);
        Py::Tuple nameArg(1);
        nameArg.setItem(0, Py::String(name));
        Py::Object handler = Py::Callable(gui.getAttr("getWorkbench")).apply(nameArg);
        if (handler.hasAttr("__Workbench__")) {
            return Py::False();
        }

        try {
            Py::Tuple noArgs;
            std::string type = Py::String(Py::Callable(handler.getAttr("GetClassName")).apply(noArgs))
                                   .as_std_string("ascii");
            auto* manager = Gui::WorkbenchManager::instance();

            if (Base::Type::fromName(type.c_str())
                    .isDerivedFrom(Gui::PythonBaseWorkbench::getClassTypeId())) {
                Gui::Workbench* workbench = manager->createWorkbench(name, type);
                handler.setAttr("__Workbench__", Py::Object(workbench->getPyObject(), true));
            }

            Py::Callable(handler.getAttr("Initialize")).apply(noArgs);

            if (!handler.hasAttr("__Workbench__")) {
                // A C++ workbench: its type exists now that Initialize() loaded its module.
                Gui::Workbench* workbench = manager->createWorkbench(name, type);
                handler.setAttr("__Workbench__", Py::Object(workbench->getPyObject(), true));
            }
        }
        catch (const Base::Exception& e) {
            throw Py::RuntimeError(e.what());
        }
        return Py::True();
    }
};

}  // namespace StudioGui

PyMOD_INIT_FUNC(StudioGui)
{
    if (!Gui::Application::Instance) {
        PyErr_SetString(PyExc_ImportError, "Cannot load Gui module in console application.");
        PyMOD_Return(nullptr);
    }
    PyObject* module = Base::Interpreter().addModule(new StudioGui::Module);
    PyMOD_Return(module);
}
