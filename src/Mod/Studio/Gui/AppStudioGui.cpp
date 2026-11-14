// SPDX-License-Identifier: LGPL-2.1-or-later
//
// StudioGui: Studio's C++ helpers for the shell, where FreeCAD offers no Python API.
// See docs/adr/0007-lazy-loading-command-catalog.md.

#include <map>
#include <string>

#include <QAbstractSpinBox>
#include <QApplication>
#include <QComboBox>
#include <QKeyEvent>
#include <QLineEdit>
#include <QPlainTextEdit>
#include <QTextEdit>

#include <CXX/Extensions.hxx>

#include <Base/Exception.h>
#include <Base/Interpreter.h>
#include <Base/PyObjectBase.h>  // PyMOD_INIT_FUNC
#include <Base/Type.h>
#include <Gui/Application.h>
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
        initialize("Studio's C++ helpers for the shell (docs/adr/0007, 0008).");
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
