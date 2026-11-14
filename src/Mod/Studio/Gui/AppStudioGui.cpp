// SPDX-License-Identifier: LGPL-2.1-or-later
//
// StudioGui: Studio's C++ helpers for the shell, where FreeCAD offers no Python API.
// See docs/adr/0007-lazy-loading-command-catalog.md.

#include <string>

#include <CXX/Extensions.hxx>

#include <Base/Exception.h>
#include <Base/Interpreter.h>
#include <Base/PyObjectBase.h>  // PyMOD_INIT_FUNC
#include <Base/Type.h>
#include <Gui/Application.h>
#include <Gui/Workbench.h>
#include <Gui/WorkbenchManager.h>

namespace StudioGui
{

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
        initialize("Studio's C++ helpers for the shell (docs/adr/0007).");
    }

private:
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
