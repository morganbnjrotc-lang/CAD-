// SPDX-License-Identifier: LGPL-2.1-or-later
//
// StudioGui: Studio's C++ helpers for the shell, where FreeCAD offers no Python API, or where Python
// can't safely reach (see style_panels). See docs/adr/0007-lazy-loading-command-catalog.md.

#include <algorithm>
#include <map>
#include <memory>
#include <optional>
#include <set>
#include <string>

#include <QAbstractSpinBox>
#include <QAction>
#include <QApplication>
#include <QBuffer>
#include <QColor>
#include <QComboBox>
#include <QIcon>
#include <QKeyEvent>
#include <QLabel>
#include <QLineEdit>
#include <QMap>
#include <QMdiArea>
#include <QMenu>
#include <QMouseEvent>
#include <QPainter>
#include <QContextMenuEvent>
#include <QPlainTextEdit>
#include <QPointer>
#include <QStatusBar>
#include <QSvgRenderer>
#include <QTabBar>
#include <QTabWidget>
#include <QTextEdit>
#include <QTimer>
#include <QToolButton>
#include <QTreeView>

#include <CXX/Extensions.hxx>

#include <Base/Exception.h>
#include <Base/Interpreter.h>
#include <Base/PyObjectBase.h>  // PyMOD_INIT_FUNC
#include <Base/ServiceProvider.h>
#include <Base/Type.h>
#include <Inventor/SbPlane.h>
#include <Inventor/SbViewportRegion.h>
#include <Inventor/SoPath.h>
#include <Inventor/SoRenderManager.h>
#include <Inventor/actions/SoGetBoundingBoxAction.h>
#include <Inventor/actions/SoSearchAction.h>
#include <Inventor/annex/FXViz/nodes/SoShadowDirectionalLight.h>
#include <Inventor/annex/FXViz/nodes/SoShadowGroup.h>
#include <Inventor/annex/FXViz/nodes/SoShadowStyle.h>
#include <Inventor/nodes/SoClipPlane.h>
#include <Inventor/nodes/SoCoordinate3.h>
#include <Inventor/nodes/SoFaceSet.h>
#include <Inventor/nodes/SoGroup.h>
#include <Inventor/nodes/SoMaterial.h>
#include <Inventor/nodes/SoMaterialBinding.h>
#include <Inventor/nodes/SoNormal.h>
#include <Inventor/nodes/SoNormalBinding.h>
#include <Inventor/nodes/SoSeparator.h>
#include <Inventor/nodes/SoShapeHints.h>
#include <Inventor/nodes/SoSwitch.h>
#include <Inventor/sensors/SoNodeSensor.h>

#include <Base/Placement.h>
#include <Base/Rotation.h>

#include <App/Application.h>
#include <App/Document.h>

#include <Gui/Action.h>
#include <Gui/Application.h>
#include <Gui/BitmapFactory.h>
#include <Gui/Command.h>
#include <Gui/Control.h>
#include <Gui/Document.h>
#include <Gui/MainWindow.h>
#include <Gui/NaviCube.h>
#include <Gui/OverlayManager.h>
#include <Gui/Inventor/Draggers/SoLinearDragger.h>
#include <Gui/PrefWidgets.h>
#include <Gui/Selection/Selection.h>
#include <Gui/Utilities.h>  // Base::Color as Coin's SbColor
#include <Gui/QuantitySpinBox.h>
#include <Gui/StyleParameters/ParameterManager.h>
#include <Gui/TaskView/TaskView.h>
#include <Gui/View3DInventor.h>
#include <Gui/View3DInventorViewer.h>
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

// Synthetic input for tests (PLAN 3.2): the active 3D view's viewer, and keys by character.
Gui::View3DInventorViewer* activeViewer()
{
    Gui::MainWindow* main = Gui::getMainWindow();
    auto* view = main ? dynamic_cast<Gui::View3DInventor*>(main->activeWindow()) : nullptr;
    if (!view) {
        throw Py::RuntimeError("no 3D view is active");
    }
    return view->getViewer();
}

int keyForCharacter(QChar c)
{
    if (c >= QLatin1Char('0') && c <= QLatin1Char('9')) {
        return Qt::Key_0 + (c.unicode() - '0');
    }
    if (c.isLetter() && c.toUpper() >= QLatin1Char('A') && c.toUpper() <= QLatin1Char('Z')) {
        return Qt::Key_A + (c.toUpper().unicode() - 'A');
    }
    switch (c.unicode()) {
        case '.':
            return Qt::Key_Period;
        case ',':
            return Qt::Key_Comma;
        case ' ':
            return Qt::Key_Space;
        case '-':
            return Qt::Key_Minus;
        case '"':
            return Qt::Key_QuoteDbl;
        default:
            return 0;
    }
}

int keyForName(const QString& name)
{
    static const QMap<QString, int> keys {
        {QStringLiteral("Tab"), Qt::Key_Tab},
        {QStringLiteral("Return"), Qt::Key_Return},
        {QStringLiteral("Escape"), Qt::Key_Escape},
        {QStringLiteral("Backspace"), Qt::Key_Backspace},
    };
    return keys.value(name, 0);
}

// Where keys go: the main window's focus widget (set even while the window isn't active, as when the
// screen is locked). A spin box's inner line edit forwards to the spin box, which FreeCAD's on-view
// size boxes watch.
QWidget* keyTarget()
{
    Gui::MainWindow* main = Gui::getMainWindow();
    QWidget* target = main ? main->focusWidget() : nullptr;
    if (target && qobject_cast<QLineEdit*>(target)
        && qobject_cast<QAbstractSpinBox*>(target->parentWidget())) {
        target = target->parentWidget();
    }
    return target;
}

// A field the user can use: on screen, or in the Tasks panel and shown with it. The panel shows only while
// a task is open (PLAN 3.10) and slides in, so right after a task starts its fields aren't visible yet.
bool inUse(QWidget* field)
{
    if (field->isVisible()) {
        return true;
    }
    QWidget* tasks = Gui::Control().taskPanel();
    return tasks && tasks->isAncestorOf(field) && field->isVisibleTo(tasks);
}

// Typing into a size box replaces its whole text, unit included, as in Fusion (PLAN 3.2, 3.5). FreeCAD
// selects only the number ("1.52| in|"): "50 mm" typed became "50 mm in". In the sketch tools' boxes in
// the 3D view (which re-select the number as they follow the mouse) Tab took that as 50 in; in a task
// panel's box (Pad's length) Return ignored it. On the first key typed while the number is selected,
// everything is selected instead; the key then replaces it, and a bare number reads in the user's units.
class SizeBoxTyping: public QObject
{
public:
    bool eventFilter(QObject* watched, QEvent* event) override
    {
        if (event->type() != QEvent::KeyPress || !watched->inherits("Gui::QuantitySpinBox")) {
            return false;
        }
        auto* key = static_cast<QKeyEvent*>(event);
        const QString text = key->text();
        if (text.isEmpty() || !text.at(0).isPrint()
            || (key->modifiers() & (Qt::ControlModifier | Qt::AltModifier))) {
            return false;
        }
        auto* box = static_cast<QWidget*>(watched);
        auto* edit = box->findChild<QLineEdit*>();
        if (!edit || !edit->hasSelectedText() || edit->selectedText() == edit->text()) {
            return false;
        }
        edit->selectAll();
        return false;  // the key goes on and replaces the selection
    }
};

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

/// Calls back once the left mouse button has been let go in the main window and the release has been
/// handled: by then Part Design's drag arrow has finished its drag (PLAN 3.5, extrude or cut by
/// direction). One call per release, however many widgets the release passes through.
class MouseReleaseWatch: public QObject
{
public:
    explicit MouseReleaseWatch(const Py::Object& callback)
        : callback(callback)
    {}

    bool eventFilter(QObject* watched, QEvent* event) override
    {
        if (event->type() == QEvent::MouseButtonRelease && !pending && watched->isWidgetType()
            && static_cast<QMouseEvent*>(event)->button() == Qt::LeftButton
            && static_cast<QWidget*>(watched)->window() == Gui::getMainWindow()) {
            pending = true;
            QTimer::singleShot(0, this, [this] { tell(); });
        }
        return false;
    }

    /// Lets go of the callback now, from Python (the GIL held): the watch itself is deleted later, from
    /// Qt's event loop, where dropping a Python object would be without the GIL.
    void release()
    {
        callback = Py::None();
    }

private:
    void tell()
    {
        pending = false;
        Base::PyGILStateLocker lock;
        if (callback.isNone()) {
            return;  // stopped since the release
        }
        try {
            Py::Callable(callback).apply(Py::Tuple());
        }
        catch (Py::Exception&) {
            Base::PyException error;  // takes the pending Python error
            error.reportException();
        }
    }

    Py::Object callback;
    bool pending = false;
};

/// Right-click on a size box in the task panel: FreeCAD's items, then Studio's (PLAN 3.6, Make
/// Default). `items(field, value)` gives Studio's labels for that box (none: FreeCAD's own menu as
/// before); `chosen(field, label, value)` is called when one is picked. Values are in the box's unit's
/// base (mm, degrees). FreeCAD's PrefQuantitySpinBox builds its menu inside its own handler with no
/// way to add to it, so Studio shows the menu instead: the box's recent values and Save Value, the
/// text field's Edit menu, then Studio's items. The menu doesn't wait (popup, not exec).
class FieldMenuGate: public QObject
{
public:
    FieldMenuGate(const Py::Object& items, const Py::Object& chosen)
        : items(items)
        , chosen(chosen)
    {}

    bool eventFilter(QObject* watched, QEvent* event) override
    {
        if (event->type() != QEvent::ContextMenu || !watched->isWidgetType()) {
            return false;
        }
        auto* box = qobject_cast<Gui::QuantitySpinBox*>(watched);
        if (!box && watched->parent()) {  // the box's own text field
            box = qobject_cast<Gui::QuantitySpinBox*>(watched->parent());
        }
        Gui::TaskView::TaskView* tasks = Gui::Control().taskPanel();
        if (!box || box->objectName().isEmpty() || !tasks || !tasks->isAncestorOf(box) || items.isNone()) {
            return false;
        }
        const std::string field = box->objectName().toStdString();
        const double value = box->rawValue();
        std::vector<std::string> labels;
        {
            Base::PyGILStateLocker lock;
            try {
                Py::Tuple args(2);
                args.setItem(0, Py::String(field));
                args.setItem(1, Py::Float(value));
                Py::Sequence result(Py::Callable(items).apply(args));
                for (Py::Sequence::size_type i = 0; i < result.length(); ++i) {
                    labels.push_back(Py::String(result[i]).as_std_string("utf-8"));
                }
            }
            catch (Py::Exception&) {
                Base::PyException error;
                error.reportException();
                return false;
            }
        }
        if (labels.empty()) {
            return false;
        }
        showMenu(box, labels, static_cast<QContextMenuEvent*>(event)->globalPos());
        return true;
    }

    /// Lets go of the callbacks now, the GIL held (see MouseReleaseWatch::release).
    void release()
    {
        items = Py::None();
        chosen = Py::None();
    }

private:
    void showMenu(Gui::QuantitySpinBox* box, const std::vector<std::string>& labels, const QPoint& at)
    {
        auto* menu = new QMenu(box);
        menu->setAttribute(Qt::WA_DeleteOnClose);
        QPointer<Gui::QuantitySpinBox> target(box);
        if (auto* pref = qobject_cast<Gui::PrefQuantitySpinBox*>(box)) {
            const QStringList history = pref->getHistory();
            for (const QString& recent : history) {  // as FreeCAD's menu: the box takes the text
                menu->addAction(recent, menu, [target, recent] {
                    if (target) {
                        if (auto* edit = target->findChild<QLineEdit*>()) {
                            edit->setText(recent);
                        }
                    }
                });
            }
            if (!history.isEmpty()) {
                menu->addSeparator();
            }
            QPointer<Gui::PrefQuantitySpinBox> prefTarget(pref);
            menu->addAction(QObject::tr("Save Value"), menu, [prefTarget] {
                if (prefTarget) {
                    prefTarget->pushToHistory();
                }
            });
        }
        if (auto* edit = box->findChild<QLineEdit*>()) {
            QMenu* editMenu = edit->createStandardContextMenu();
            editMenu->setTitle(QObject::tr("Edit"));
            editMenu->setParent(menu, editMenu->windowFlags());
            menu->addMenu(editMenu);
        }
        menu->addSeparator();
        const std::string field = box->objectName().toStdString();
        for (const std::string& label : labels) {
            menu->addAction(QString::fromStdString(label), menu, [this, target, field, label] {
                if (!target || chosen.isNone()) {
                    return;
                }
                Base::PyGILStateLocker lock;
                try {
                    Py::Tuple args(3);
                    args.setItem(0, Py::String(field));
                    args.setItem(1, Py::String(label));
                    args.setItem(2, Py::Float(target->rawValue()));
                    Py::Callable(chosen).apply(args);
                }
                catch (Py::Exception&) {
                    Base::PyException error;
                    error.reportException();
                }
            });
        }
        menu->popup(at);
    }

    Py::Object items;
    Py::Object chosen;
};

/// One-click section view (PLAN 3.7): FreeCAD's clipping plane in a 3D view (toggleClippingPlane, no
/// manipulator), with the arrow Extrude drags (Gui::SoLinearDraggerContainer) on it to move the plane
/// along its normal. The view keeps the side the plane's normal points to; the arrow points the other
/// way, out of what is kept. The arrow goes just before the clipping plane in the view's scene, so it
/// isn't cut away itself.
class SectionView
{
public:
    bool on(Gui::View3DInventor* target, const SbVec3f& point, const SbVec3f& normal, float size)
    {
        off();
        Gui::View3DInventorViewer* viewer = target->getViewer();
        keep = normal;
        keep.normalize();
        base = point;
        viewer->toggleClippingPlane(1, false, true, placement(point));
        if (!findClipPlane(viewer)) {
            viewer->toggleClippingPlane(0);
            return false;
        }
        update(0.0F);
        view = target;

        arrow = new Gui::SoLinearDraggerContainer;
        arrow->ref();
        arrow->translation = base;
        arrow->setPointerDirection(-keep);
        Gui::SoLinearDragger* dragger = arrow->getDragger();
        dragger->labelVisible = false;
        dragger->instantiateBaseGeometry();
        const float scale = std::max(size / 20.0F, 0.05F);
        dragger->geometryScale = SbVec3f(scale, scale, scale);
        dragger->translationIncrement = std::max(size / 400.0F, 0.001F);  // smooth, not 1 mm steps
        auto* manager = Base::provideService<Gui::StyleParameters::ParameterManager>();
        if (manager) {  // the accent, as Extrude's arrow (Gui::LinearGizmo::updateColorTheme)
            const Gui::StyleParameters::ParameterDefinition<Base::Color> base {"LinearGizmoBaseColor", Base::Color(1.0F, 0.0F, 0.0F)};
            const Gui::StyleParameters::ParameterDefinition<Base::Color> active {"LinearGizmoActiveColor", Base::Color(1.0F, 1.0F, 0.0F)};
            dragger->color = manager->resolve(base).asValue<SbColor>();
            dragger->activeColor = manager->resolve(active).asValue<SbColor>();
        }
        dragger->addMotionCallback(&SectionView::dragged, this);
        parent->insertChild(arrow, parent->findChild(clip));
        return true;
    }

    void off()
    {
        if (view) {
            if (arrow && parent && parent->findChild(arrow) >= 0) {
                parent->removeChild(arrow);
            }
            view->getViewer()->toggleClippingPlane(0);
        }
        if (arrow) {
            arrow->getDragger()->removeMotionCallback(&SectionView::dragged, this);
            arrow->unref();
        }
        arrow = nullptr;
        clip = nullptr;
        parent = nullptr;
        view = nullptr;
    }

    bool isOn()
    {
        if (!view && (arrow || clip)) {
            off();  // its view was closed: FreeCAD deleted the plane with the view's scene
        }
        return view && clip;
    }

    SbVec3f point() const
    {
        return current;
    }

    SbVec3f normal() const
    {
        return keep;
    }

    /// As dragging the arrow by `distance` along itself would (tests).
    void drag(float distance)
    {
        if (arrow) {
            arrow->getDragger()->translation = SbVec3f(0.0F, distance, 0.0F);
            update(distance);
        }
    }

private:
    static void dragged(void* data, SoDragger* dragger)
    {
        auto* self = static_cast<SectionView*>(data);
        self->update(static_cast<Gui::SoLinearDragger*>(dragger)->translation.getValue()[1]);
    }

    void update(float along)
    {
        current = base - keep * along;  // the arrow points along -keep
        if (clip) {
            clip->plane.setValue(SbPlane(keep, current));
        }
    }

    /// The plane FreeCAD's toggleClippingPlane makes keeps the side of rotation * (0, 0, -1).
    Base::Placement placement(const SbVec3f& at) const
    {
        Base::Rotation turn(Base::Vector3d(0, 0, -1), Base::Vector3d(keep[0], keep[1], keep[2]));
        return Base::Placement(Base::Vector3d(at[0], at[1], at[2]), turn);
    }

    bool findClipPlane(Gui::View3DInventorViewer* viewer)
    {
        SoSearchAction search;
        search.setType(SoClipPlane::getClassTypeId());
        search.setInterest(SoSearchAction::FIRST);
        search.apply(viewer->getSceneGraph());
        SoPath* path = search.getPath();
        if (!path || path->getLength() < 2) {
            return false;
        }
        clip = static_cast<SoClipPlane*>(path->getTail());
        parent = dynamic_cast<SoGroup*>(path->getNodeFromTail(1));
        return parent != nullptr;
    }

    QPointer<Gui::View3DInventor> view;
    Gui::SoLinearDraggerContainer* arrow = nullptr;
    SoClipPlane* clip = nullptr;  // FreeCAD's, owned by the viewer
    SoGroup* parent = nullptr;
    SbVec3f base, keep, current;
};

/// Display looks (PLAN 3.8: Pretty, Gray Box, Realistic). FreeCAD's viewer draws no shadows; Coin has them
/// (SoShadowGroup: variance shadow maps, per-pixel lighting), which FreeCAD never uses. A view's objects
/// (FreeCAD's "ObjectGroup", which holds every view provider's scene) move into a shadow group with a
/// directional shadow light and a floor under them that takes their shadow; a gray material, or
/// highlights, can override theirs. FreeCAD only adds and removes the object group's children, so where it
/// sits doesn't matter to it. Destroyed, the look puts the objects back where they were.
class ViewLook
{
public:
    enum Material
    {
        Own = -1,
        Gray = 0,
        Shiny = 1
    };

    ViewLook(SoGroup* parent, SoGroup* objects)
        : parent(parent)
        , objects(objects)
    {
        parent->ref();
        objects->ref();
        shadows = new SoShadowGroup;
        shadows->ref();
        shadows->setName("StudioLook");
        shadows->quality = 1.0F;  // per-pixel lighting
        shadows->precision = 0.8F;
        shadows->intensity = 0.45F;
        shadows->smoothBorder = 0.5F;
        shadows->addChild(style(SoShadowStyle::NO_SHADOWING));
        light = new SoShadowDirectionalLight;
        light->direction.setValue(0.35F, 0.55F, -1.0F);  // from above, a little from the front left
        light->intensity = 0.35F;
        shadows->addChild(light);
        shadows->addChild(style(SoShadowStyle::CASTS_SHADOW_AND_SHADOWED));
        auto* model = new SoSeparator;  // keeps the material override off the floor
        model->renderCaching = SoSeparator::OFF;
        materials = new SoSwitch;
        materials->whichChild = SO_SWITCH_NONE;
        materials->addChild(grayMaterial());
        materials->addChild(shinyMaterial());
        model->addChild(materials);
        model->addChild(objects);
        shadows->addChild(model);
        shadows->addChild(style(SoShadowStyle::SHADOWED));
        auto* floorPart = new SoSeparator;
        auto* hints = new SoShapeHints;  // one-sided: seen from below, the model shows through
        hints->vertexOrdering = SoShapeHints::COUNTERCLOCKWISE;
        hints->shapeType = SoShapeHints::SOLID;
        floorPart->addChild(hints);
        floorColor = new SoMaterial;
        floorColor->specularColor.setValue(0.0F, 0.0F, 0.0F);
        floorPart->addChild(floorColor);
        floor = new SoCoordinate3;
        floorPart->addChild(floor);
        auto* normal = new SoNormal;
        normal->vector.setValue(0.0F, 0.0F, 1.0F);
        floorPart->addChild(normal);
        auto* binding = new SoNormalBinding;
        binding->value = SoNormalBinding::OVERALL;
        floorPart->addChild(binding);
        auto* face = new SoFaceSet;
        face->numVertices.setValue(4);
        floorPart->addChild(face);
        shadows->addChild(floorPart);

        parent->replaceChild(objects, shadows);
        sensor = new SoNodeSensor(&ViewLook::changed, this);  // the floor follows the model
        sensor->attach(objects);
        fit();
    }

    ~ViewLook()
    {
        sensor->detach();
        delete sensor;
        if (parent->findChild(shadows) >= 0) {
            parent->replaceChild(shadows, objects);
        }
        shadows->unref();
        objects->unref();
        parent->unref();
    }

    ViewLook(const ViewLook&) = delete;
    ViewLook& operator=(const ViewLook&) = delete;

    void set(Material material, const QColor& floorRgb)
    {
        materials->whichChild = material == Own ? SO_SWITCH_NONE : int(material);
        // lit by the headlight and the shadow light, the floor shows about as bright as the background
        const float dim = 0.8F;
        floorColor->diffuseColor.setValue(dim * float(floorRgb.redF()), dim * float(floorRgb.greenF()),
                                          dim * float(floorRgb.blueF()));
    }

    Material material() const
    {
        int which = materials->whichChild.getValue();
        return which == SO_SWITCH_NONE ? Own : Material(which);
    }

    /// The floor's height, or no floor (nothing to draw).
    std::optional<float> floorHeight() const
    {
        if (floor->point.getNum() == 0) {
            return std::nullopt;
        }
        return floor->point[0][2];
    }

private:
    static SoShadowStyle* style(int which)
    {
        auto* node = new SoShadowStyle;
        node->style = which;
        return node;
    }

    static SoNode* grayMaterial()
    {
        auto* group = new SoGroup;
        auto* gray = new SoMaterial;  // clay: one neutral gray, a little sheen
        gray->ambientColor.setValue(0.25F, 0.25F, 0.26F);
        gray->diffuseColor.setValue(0.62F, 0.63F, 0.65F);  // lit tops stay apart from the floor
        gray->specularColor.setValue(0.12F, 0.12F, 0.12F);
        gray->shininess = 0.2F;
        gray->emissiveColor.setIgnored(true);
        gray->transparency.setIgnored(true);
        gray->setOverride(true);
        auto* once = new SoMaterialBinding;  // not per face
        once->value = SoMaterialBinding::OVERALL;
        once->setOverride(true);
        group->addChild(gray);
        group->addChild(once);
        return group;
    }

    static SoNode* shinyMaterial()
    {
        auto* shine = new SoMaterial;  // highlights on the parts' own colors
        shine->specularColor.setValue(0.45F, 0.45F, 0.45F);
        shine->shininess = 0.55F;
        shine->ambientColor.setIgnored(true);
        shine->diffuseColor.setIgnored(true);
        shine->emissiveColor.setIgnored(true);
        shine->transparency.setIgnored(true);
        shine->setOverride(true);
        return shine;
    }

    static void changed(void* data, SoSensor* /*sensor*/)
    {
        static_cast<ViewLook*>(data)->fit();
    }

    /// The floor just under the model and well beyond it; the shadow light covers the model and its shadow.
    void fit()
    {
        SoGetBoundingBoxAction measure(SbViewportRegion(100, 100));
        measure.apply(objects);
        const SbBox3f box = measure.getBoundingBox();
        if (box.isEmpty()) {
            floor->point.setNum(0);
            return;
        }
        float dx = 0, dy = 0, dz = 0;
        box.getSize(dx, dy, dz);
        const float size = std::max({dx, dy, dz, 1e-3F});
        const SbVec3f center = box.getCenter();
        const float reach = 6.0F * size;
        const float z = box.getMin()[2] - 0.002F * size;
        const SbVec3f corners[4] = {
            SbVec3f(center[0] - reach, center[1] - reach, z),
            SbVec3f(center[0] + reach, center[1] - reach, z),
            SbVec3f(center[0] + reach, center[1] + reach, z),
            SbVec3f(center[0] - reach, center[1] + reach, z),
        };
        floor->point.setValues(0, 4, corners);
        light->bboxCenter = center;
        light->bboxSize = SbVec3f(1.6F * size, 1.6F * size, 1.6F * size);  // the shadow map is 2048 px at most
    }

    SoGroup* parent;
    SoGroup* objects;
    SoShadowGroup* shadows = nullptr;
    SoShadowDirectionalLight* light = nullptr;
    SoSwitch* materials = nullptr;
    SoMaterial* floorColor = nullptr;
    SoCoordinate3* floor = nullptr;
    SoNodeSensor* sensor = nullptr;
};

/// Construction on and off while sketching (PLAN 3.13; Fusion's X). It runs FreeCAD's
/// Sketcher_ToggleConstruction: with sketch geometry selected that switches the geometry to or from
/// construction, otherwise it switches what gets drawn next. Python can't read whether construction
/// is on, so this command is a C++ one: FreeCAD tells the commands registered for its
/// "ToggleConstruction" mode whenever construction goes on or off (the toggle, another sketch edited,
/// editing ends), and this one keeps that for Studio's toolbar and tells it (watch_construction).
class ConstructionCommand: public Gui::Command
{
public:
    ConstructionCommand()
        : Command("Studio_Construction")
    {
        sAppModule = "Studio";
        sGroup = "Studio";
        sMenuText = QT_TR_NOOP("Construction");
        sToolTipText = QT_TR_NOOP(
            "Draws construction geometry from now on, or turns the selected sketch geometry into "
            "construction geometry and back"
        );
        sWhatsThis = "Studio_Construction";
        sStatusTip = sToolTipText;
        sPixmap = "Sketcher_ToggleConstruction";
        eType = ForEdit | NoTransaction;  // FreeCAD's toggle opens its own undo step
    }

    const char* className() const override
    {
        return "StudioGui::ConstructionCommand";
    }

    bool isActive() override
    {
        Gui::Command* toggle = Gui::Application::Instance->commandManager().getCommandByName(
            "Sketcher_ToggleConstruction"
        );
        return toggle && toggle->isActive();
    }

    /// mode: FreeCAD's SketcherGui::GeometryCreationMode (0 normal, 1 construction).
    void updateAction(int mode) override
    {
        on = mode == 1;
        if (Gui::Action* action = getAction()) {
            action->setCheckable(true);
            action->setChecked(on);
        }
        if (!listener) {
            return;
        }
        Base::PyGILStateLocker lock;
        try {
            Py::Callable(listener).apply(Py::Tuple());
        }
        catch (Py::Exception&) {
            Base::PyException error;  // takes the pending Python error
            error.reportException();
        }
    }

    static inline bool on = false;
    static inline PyObject* listener = nullptr;  // a new reference while set

protected:
    void activated(int) override
    {
        Gui::Application::Instance->commandManager().runCommandByName("Sketcher_ToggleConstruction");
    }
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
            "add_commands",
            &Module::addCommands,
            "add_commands()\n\n"
            "Registers Studio's C++ commands (once): Studio_Construction (PLAN 3.13)."
        );
        add_varargs_method(
            "construction_mode",
            &Module::constructionMode,
            "construction_mode() -> bool\n\n"
            "Whether the sketch being edited draws construction geometry (Studio_Construction)."
        );
        add_varargs_method(
            "watch_construction",
            &Module::watchConstruction,
            "watch_construction(callback)\n\n"
            "callback() whenever construction goes on or off; None stops."
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
            "watch_mouse_release",
            &Module::watchMouseRelease,
            "watch_mouse_release(callback) -> int\n\n"
            "callback() once the left mouse button has been let go in the main window and the release\n"
            "handled (a drag arrow's drag has finished by then); once per release. Returns an id for\n"
            "unwatch_mouse_release()."
        );
        add_varargs_method(
            "unwatch_mouse_release",
            &Module::unwatchMouseRelease,
            "unwatch_mouse_release(id): stops a watch_mouse_release()."
        );
        add_varargs_method(
            "section",
            &Module::section,
            "section(px, py, pz, nx, ny, nz, size) -> bool\n\n"
            "Cuts the active 3D view with the plane through (px, py, pz) keeping the side the normal\n"
            "(nx, ny, nz) points to, and puts Extrude's arrow on it to drag it (PLAN 3.7); `size` (mm,\n"
            "the model's) sizes the arrow. Replaces a section already on. False without a 3D view."
        );
        add_varargs_method(
            "set_look",
            &Module::setLook,
            "set_look(shadows, gray, shiny, floor_color)\n\n"
            "Studio's look on every open 3D view, and on views opened later when called again (PLAN 3.8):\n"
            "shadows on a floor under the model (floor_color \"#RRGGBB\"), every part in one gray, or\n"
            "highlights on the parts' own colors. All false takes it off."
        );
        add_varargs_method(
            "look",
            &Module::look,
            "look() -> (shadows, gray, shiny, floor height or None)\n\n"
            "For tests: Studio's look on the active 3D view (set_look)."
        );
        add_varargs_method(
            "draw_style",
            &Module::drawStyle,
            "draw_style() -> str or None\n\n"
            "How the active 3D view draws the model: FreeCAD's draw style (\"As Is\", \"Shaded\",\n"
            "\"Hidden Line\", \"Wireframe\"…), which its Python API can set but not read (PLAN 3.8)."
        );
        add_varargs_method(
            "section_off",
            &Module::sectionOff,
            "section_off(): ends the section view."
        );
        add_varargs_method(
            "section_plane",
            &Module::sectionPlane,
            "section_plane() -> ((px, py, pz), (nx, ny, nz)) or None\n\n"
            "Where the section plane is now (dragged or not) and the side it keeps; None while off\n"
            "(also once its view closed)."
        );
        add_varargs_method(
            "section_drag",
            &Module::sectionDrag,
            "section_drag(distance)\n\n"
            "For tests: moves the section as dragging its arrow by `distance` mm along itself would\n"
            "(negative: back into what is kept)."
        );
        add_varargs_method(
            "add_field_menu",
            &Module::addFieldMenu,
            "add_field_menu(items, chosen)\n\n"
            "Right-clicking a size box in the task panel shows FreeCAD's items (recent values, Save Value,\n"
            "Edit) and then Studio's: items(field, value) -> labels for that box (none: FreeCAD's own\n"
            "menu); chosen(field, label, value) when one is picked. `field` is the box's object name,\n"
            "values in its unit's base (mm, degrees). Replaces an earlier pair (PLAN 3.6)."
        );
        add_varargs_method(
            "right_click_field",
            &Module::rightClickField,
            "right_click_field(object_name)\n\n"
            "For tests: right-clicks the middle of the visible size box with that object name (the event\n"
            "is posted, as the window system's are). KeyError if none shows."
        );
        add_varargs_method(
            "choose_popup",
            &Module::choosePopup,
            "choose_popup(label) -> bool\n\n"
            "For tests: picks the item with that text (without '&') in the menu open now, as a click\n"
            "would (an item showing its key after a tab matches by its name too). False if no menu is open\n"
            "or it has no such enabled item."
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
        add_varargs_method(
            "install_size_box_typing",
            &Module::installSizeBoxTyping,
            "install_size_box_typing()\n\n"
            "From now on, typing into a size box (the boxes sketch tools show while drawing, a task\n"
            "panel's lengths) replaces its whole text, unit included, as in Fusion (PLAN 3.2, 3.5).\n"
            "Once per session."
        );
        add_varargs_method(
            "view_point",
            &Module::viewPoint,
            "view_point(x, y, z) -> (px, py)\n\n"
            "For tests: where a point (document coordinates, mm) shows in the active 3D view, in the view\n"
            "widget's pixels from its top left."
        );
        add_varargs_method(
            "view_size",
            &Module::viewSize,
            "view_size() -> (width, height)\n\n"
            "For tests: the active 3D view widget's size in pixels."
        );
        add_varargs_method(
            "view_mouse",
            &Module::viewMouse,
            "view_mouse(action, px, py)\n\n"
            "For tests: 'move', 'press', 'release' or 'click' (left button), or 'right_click', at a pixel\n"
            "of the active 3D view."
        );
        add_varargs_method(
            "popup_menu",
            &Module::popupMenu,
            "popup_menu() -> list of str or None\n\n"
            "For tests: the items of the menu open now (a right-click menu), without the '&' of their\n"
            "shortcut letters; None if no menu is open."
        );
        add_varargs_method(
            "close_popups",
            &Module::closePopups,
            "close_popups() -> int\n\n"
            "For tests: closes every open menu, as clicking elsewhere would. Returns how many it closed."
        );
        add_varargs_method(
            "type_keys",
            &Module::typeKeys,
            "type_keys(text)\n\n"
            "For tests: types `text` into the main window's focus widget; keys by name in braces: {Tab},\n"
            "{Return}, {Escape}, {Backspace}. Raises RuntimeError if nothing has the focus."
        );
        add_varargs_method(
            "focus_field",
            &Module::focusField,
            "focus_field(object_name)\n\n"
            "For tests: focuses the main window's visible field with that object name, as FreeCAD does\n"
            "when it opens a task (a size field gets its number selected). Raises KeyError if none."
        );
        add_varargs_method(
            "set_field",
            &Module::setField,
            "set_field(object_name, value) -> bool\n\n"
            "Sets the main window's visible size box with that object name (a task panel's \"lengthEdit\")\n"
            "to `value`, in its unit's base (millimeters for a length), as typing it would: the panel\n"
            "takes it. False if no such box shows."
        );
        add_varargs_method(
            "focus_widget",
            &Module::focusWidget,
            "focus_widget() -> (class name, is a size box in the 3D view, its text) or None\n\n"
            "For tests: what keys typed now would go to."
        );
        add_varargs_method(
            "start_picking",
            &Module::startPicking,
            "start_picking() -> bool\n\n"
            "Presses the open task panel's \"Select\" button (Part Design's Fillet and Chamfer), so clicks\n"
            "on the model add or take out edges straight away, as in Fusion (PLAN 3.11). Does nothing if\n"
            "it is off limits (\"Use All Edges\") or already pressed. Returns True if it pressed it."
        );
        add_varargs_method(
            "selection_gate",
            &Module::selectionGate,
            "selection_gate() -> bool\n\n"
            "Whether FreeCAD limits what a click can pick (a selection gate): a task panel picking something\n"
            "itself, as Extrude's face to extrude up to or Revolve's axis. Studio leaves those clicks to it\n"
            "(PLAN 3.16)."
        );
        add_varargs_method(
            "set_drawing_method",
            &Module::setDrawingMethod,
            "set_drawing_method(index) -> bool\n\n"
            "Switches the sketch tool being used to another way of drawing (PLAN 3.12): picks `index` in\n"
            "the first list of the tool's settings panel, the one FreeCAD's M key steps through (a\n"
            "rectangle: 0 two corners, 1 center, 2 three corners, 3 center and two corners). False if no\n"
            "tool panel shows that list; ValueError if the index is outside it."
        );
        add_varargs_method(
            "set_tool_parameter",
            &Module::setToolParameter,
            "set_tool_parameter(number, value) -> bool\n\n"
            "Sets the number box `number` (1 to 10) of the sketch tool's settings panel, as typing it would\n"
            "(a pattern's Elements is 1). False if no tool panel shows that box."
        );
        add_varargs_method(
            "style_color",
            &Module::styleColor,
            "style_color(token) -> '#RRGGBB' or None\n\n"
            "The color a FreeCAD style token gives, as FreeCAD's own users of it read it (e.g. Part\n"
            "Design's drag arrows, LinearGizmoBaseColor); None if no source defines the token."
        );
        add_varargs_method(
            "reload_style_tokens",
            &Module::reloadStyleTokens,
            "reload_style_tokens()\n\n"
            "FreeCAD keeps each style token's color once it has worked it out: makes it work them out\n"
            "again, after Studio changed the tokens (a switch between light and dark)."
        );
        add_varargs_method(
            "tasks_room",
            &Module::tasksRoom,
            "tasks_room() -> (area_height, cube)\n\n"
            "The main area's height as FreeCAD lays its floating panels out (less the tab bar) and the\n"
            "navigation cube's size, in px: what sizing the Tasks panel takes (PLAN 3.10)."
        );
        add_varargs_method(
            "follow_tasks",
            &Module::followTasks,
            "follow_tasks() -> bool\n\n"
            "Has a solid Tasks panel (FreeCAD's \"Auto task\" mode) hide when its task ends (PLAN 3.10). FreeCAD\n"
            "never hides a floating panel holding the keyboard focus, and a task's fields have it (Extrude's\n"
            "length): once the task has ended the focus sits on the empty task view. It goes back to the 3D\n"
            "view, and FreeCAD checks its panels again, which it does itself on the task view's signal only\n"
            "when another panel shares the Tasks panel's side (OverlayManager::onTaskViewUpdate). Once; False\n"
            "if there is no task view."
        );
        add_varargs_method(
            "tasks_panel_rect",
            &Module::tasksPanelRect,
            "tasks_panel_rect() -> (x, y, width, height) or None\n\n"
            "For tests: where the floating Tasks panel (FreeCAD's OverlayRight) shows, in the main area's\n"
            "pixels from its top left; None while it's hidden."
        );
        initialize("Studio's C++ helpers for the shell (docs/adr/0007, 0008, 0010).");
    }

private:
    std::map<long, KeyEventGate*> gates;
    std::map<long, MouseReleaseWatch*> releaseWatches;
    FieldMenuGate* fieldMenu = nullptr;
    QPointer<Gui::TaskView::TaskView> followedTasks;  // follow_tasks
    SectionView sectionView;
    // set_look: each 3D view's look, dropped when the view closes
    std::map<Gui::View3DInventor*, std::unique_ptr<ViewLook>> looks;
    long nextGateId = 1;
    SizeBoxTyping* sizeBoxTyping = nullptr;

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

    Py::Object watchMouseRelease(const Py::Tuple& args)
    {
        PyObject* callback = nullptr;
        if (!PyArg_ParseTuple(args.ptr(), "O", &callback)) {
            throw Py::Exception();
        }
        if (!PyCallable_Check(callback)) {
            throw Py::TypeError("watch_mouse_release() needs a callable");
        }
        auto* watch = new MouseReleaseWatch(Py::Object(callback));
        qApp->installEventFilter(watch);
        const long id = nextGateId++;
        releaseWatches[id] = watch;
        return Py::Long(id);
    }

    Py::Object unwatchMouseRelease(const Py::Tuple& args)
    {
        long id = 0;
        if (!PyArg_ParseTuple(args.ptr(), "l", &id)) {
            throw Py::Exception();
        }
        auto found = releaseWatches.find(id);
        if (found != releaseWatches.end()) {
            qApp->removeEventFilter(found->second);
            found->second->release();
            found->second->deleteLater();  // it may be the one calling back now
            releaseWatches.erase(found);
        }
        return Py::None();
    }

    Py::Object section(const Py::Tuple& args)
    {
        float px = 0, py = 0, pz = 0, nx = 0, ny = 0, nz = 0, size = 0;
        if (!PyArg_ParseTuple(args.ptr(), "fffffff", &px, &py, &pz, &nx, &ny, &nz, &size)) {
            throw Py::Exception();
        }
        auto* view = qobject_cast<Gui::View3DInventor*>(Gui::getMainWindow()->activeWindow());
        if (!view || SbVec3f(nx, ny, nz).length() < 1e-9F) {
            return Py::False();
        }
        return Py::Boolean(sectionView.on(view, SbVec3f(px, py, pz), SbVec3f(nx, ny, nz), size));
    }

    Py::Object setLook(const Py::Tuple& args)
    {
        PyObject* shadowsArg = nullptr;
        PyObject* grayArg = nullptr;
        PyObject* shinyArg = nullptr;
        char* floorHex = nullptr;
        if (!PyArg_ParseTuple(args.ptr(), "OOOs", &shadowsArg, &grayArg, &shinyArg, &floorHex)) {
            throw Py::Exception();
        }
        const bool shadows = PyObject_IsTrue(shadowsArg) != 0;
        const auto material = PyObject_IsTrue(grayArg) ? ViewLook::Gray
            : PyObject_IsTrue(shinyArg)                 ? ViewLook::Shiny
                                                        : ViewLook::Own;
        const QColor floorRgb(QString::fromUtf8(floorHex));
        for (auto* view : allViews()) {
            auto found = looks.find(view);
            if (!shadows) {
                if (found != looks.end()) {
                    looks.erase(found);  // puts the objects back
                }
                continue;
            }
            if (found == looks.end()) {
                auto look = makeLook(view);
                if (!look) {
                    continue;
                }
                found = looks.emplace(view, std::move(look)).first;
                QObject::connect(view, &QObject::destroyed, [this, view]() { looks.erase(view); });
            }
            found->second->set(material, floorRgb);
        }
        return Py::None();
    }

    Py::Object look(const Py::Tuple& args)
    {
        if (!PyArg_ParseTuple(args.ptr(), "")) {
            throw Py::Exception();
        }
        auto* view = qobject_cast<Gui::View3DInventor*>(Gui::getMainWindow()->activeWindow());
        auto found = view ? looks.find(view) : looks.end();
        if (found == looks.end()) {
            return Py::TupleN(Py::False(), Py::False(), Py::False(), Py::None());
        }
        const ViewLook& viewLook = *found->second;
        const auto height = viewLook.floorHeight();
        return Py::TupleN(
            Py::True(),
            Py::Boolean(viewLook.material() == ViewLook::Gray),
            Py::Boolean(viewLook.material() == ViewLook::Shiny),
            height ? Py::Object(Py::Float(*height)) : Py::None()
        );
    }

    static std::vector<Gui::View3DInventor*> allViews()
    {
        std::vector<Gui::View3DInventor*> views;
        for (App::Document* document : App::GetApplication().getDocuments()) {
            Gui::Document* gui = Gui::Application::Instance->getDocument(document);
            if (!gui) {
                continue;
            }
            for (Gui::MDIView* view : gui->getMDIViewsOfType(Gui::View3DInventor::getClassTypeId())) {
                views.push_back(static_cast<Gui::View3DInventor*>(view));
            }
        }
        return views;
    }

    static std::unique_ptr<ViewLook> makeLook(Gui::View3DInventor* view)
    {
        SoSearchAction search;
        search.setName(SbName("ObjectGroup"));  // FreeCAD's group of every view provider's scene
        search.setInterest(SoSearchAction::FIRST);
        search.apply(view->getViewer()->getSceneGraph());
        SoPath* path = search.getPath();
        if (!path || path->getLength() < 2) {
            return nullptr;
        }
        auto* objects = dynamic_cast<SoGroup*>(path->getTail());
        auto* parent = dynamic_cast<SoGroup*>(path->getNodeFromTail(1));
        if (!objects || !parent) {
            return nullptr;
        }
        return std::make_unique<ViewLook>(parent, objects);
    }

    Py::Object drawStyle(const Py::Tuple& args)
    {
        if (!PyArg_ParseTuple(args.ptr(), "")) {
            throw Py::Exception();
        }
        auto* view = qobject_cast<Gui::View3DInventor*>(Gui::getMainWindow()->activeWindow());
        if (!view) {
            return Py::None();
        }
        return Py::String(view->getViewer()->getOverrideMode());
    }

    Py::Object sectionOff(const Py::Tuple& args)
    {
        if (!PyArg_ParseTuple(args.ptr(), "")) {
            throw Py::Exception();
        }
        sectionView.off();
        return Py::None();
    }

    Py::Object sectionPlane(const Py::Tuple& args)
    {
        if (!PyArg_ParseTuple(args.ptr(), "")) {
            throw Py::Exception();
        }
        if (!sectionView.isOn()) {
            return Py::None();
        }
        const SbVec3f p = sectionView.point();
        const SbVec3f n = sectionView.normal();
        return Py::TupleN(
            Py::TupleN(Py::Float(p[0]), Py::Float(p[1]), Py::Float(p[2])),
            Py::TupleN(Py::Float(n[0]), Py::Float(n[1]), Py::Float(n[2]))
        );
    }

    Py::Object sectionDrag(const Py::Tuple& args)
    {
        float distance = 0;
        if (!PyArg_ParseTuple(args.ptr(), "f", &distance)) {
            throw Py::Exception();
        }
        sectionView.drag(distance);
        return Py::None();
    }

    Py::Object addFieldMenu(const Py::Tuple& args)
    {
        PyObject* items = nullptr;
        PyObject* chosen = nullptr;
        if (!PyArg_ParseTuple(args.ptr(), "OO", &items, &chosen)) {
            throw Py::Exception();
        }
        if (!PyCallable_Check(items) || !PyCallable_Check(chosen)) {
            throw Py::TypeError("add_field_menu() needs two callables");
        }
        if (fieldMenu) {
            qApp->removeEventFilter(fieldMenu);
            fieldMenu->release();
            fieldMenu->deleteLater();
        }
        fieldMenu = new FieldMenuGate(Py::Object(items), Py::Object(chosen));
        qApp->installEventFilter(fieldMenu);
        return Py::None();
    }

    Py::Object rightClickField(const Py::Tuple& args)
    {
        char* name = nullptr;
        if (!PyArg_ParseTuple(args.ptr(), "s", &name)) {
            throw Py::Exception();
        }
        for (auto* box : Gui::getMainWindow()->findChildren<Gui::QuantitySpinBox*>(QString::fromUtf8(name))) {
            if (!box->isVisible()) {
                continue;
            }
            const QPoint local = box->rect().center();
            // Posted, as the window system delivers it: a menu that waits (exec) then runs from the
            // event loop, where a test's timer can still read and close it.
            QCoreApplication::postEvent(
                box,
                new QContextMenuEvent(QContextMenuEvent::Mouse, local, box->mapToGlobal(local))
            );
            return Py::None();
        }
        throw Py::KeyError(std::string("no visible size box named ") + name);
    }

    Py::Object choosePopup(const Py::Tuple& args)
    {
        char* label = nullptr;
        if (!PyArg_ParseTuple(args.ptr(), "s", &label)) {
            throw Py::Exception();
        }
        auto* menu = qobject_cast<QMenu*>(QApplication::activePopupWidget());
        if (!menu) {
            return Py::False();
        }
        const QString wanted = QString::fromUtf8(label);
        for (QAction* action : menu->actions()) {
            // The name alone also matches an item showing its key after a tab ("Section\tX").
            const QString text = QString(action->text()).remove(QLatin1Char('&'));
            if ((text == wanted || text.section(QLatin1Char('\t'), 0, 0) == wanted) && action->isEnabled()) {
                menu->close();
                action->trigger();
                return Py::True();
            }
        }
        return Py::False();
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

    Py::Object installSizeBoxTyping(const Py::Tuple& args)
    {
        if (!PyArg_ParseTuple(args.ptr(), "")) {
            throw Py::Exception();
        }
        if (!sizeBoxTyping) {
            sizeBoxTyping = new SizeBoxTyping();
            qApp->installEventFilter(sizeBoxTyping);
        }
        return Py::None();
    }

    Py::Object viewPoint(const Py::Tuple& args)
    {
        double x = 0;
        double y = 0;
        double z = 0;
        if (!PyArg_ParseTuple(args.ptr(), "ddd", &x, &y, &z)) {
            throw Py::Exception();
        }
        Gui::View3DInventorViewer* viewer = activeViewer();
        const SbVec2s point = viewer->getPointOnViewport(SbVec3f(float(x), float(y), float(z)));
        const SbVec2s size = viewer->getSoRenderManager()->getViewportRegion().getViewportSizePixels();
        const double ratio = viewer->getGLWidget()->devicePixelRatioF();
        Py::Tuple result(2);
        result.setItem(0, Py::Float(point[0] / ratio));
        result.setItem(1, Py::Float((size[1] - point[1] - 1) / ratio));
        return result;
    }

    Py::Object viewSize(const Py::Tuple& args)
    {
        if (!PyArg_ParseTuple(args.ptr(), "")) {
            throw Py::Exception();
        }
        QWidget* widget = activeViewer()->getGLWidget();
        Py::Tuple result(2);
        result.setItem(0, Py::Long(widget->width()));
        result.setItem(1, Py::Long(widget->height()));
        return result;
    }

    Py::Object viewMouse(const Py::Tuple& args)
    {
        char* action = nullptr;
        double px = 0;
        double py = 0;
        if (!PyArg_ParseTuple(args.ptr(), "sdd", &action, &px, &py)) {
            throw Py::Exception();
        }
        QWidget* widget = activeViewer()->getGLWidget();
        const QPointF local(px, py);
        const QPointF global = widget->mapToGlobal(local);
        auto send = [&](QEvent::Type type, Qt::MouseButton button, Qt::MouseButtons buttons) {
            QMouseEvent event(type, local, global, button, buttons, Qt::NoModifier);
            QApplication::sendEvent(widget, &event);
        };
        const std::string what(action);
        if (what == "move") {
            send(QEvent::MouseMove, Qt::NoButton, Qt::NoButton);
        }
        else if (what == "press" || what == "click") {
            send(QEvent::MouseMove, Qt::NoButton, Qt::NoButton);
            send(QEvent::MouseButtonPress, Qt::LeftButton, Qt::LeftButton);
            if (what == "click") {
                send(QEvent::MouseButtonRelease, Qt::LeftButton, Qt::NoButton);
            }
        }
        else if (what == "release") {
            send(QEvent::MouseButtonRelease, Qt::LeftButton, Qt::NoButton);
        }
        else if (what == "right_click") {
            send(QEvent::MouseMove, Qt::NoButton, Qt::NoButton);
            send(QEvent::MouseButtonPress, Qt::RightButton, Qt::RightButton);
            send(QEvent::MouseButtonRelease, Qt::RightButton, Qt::NoButton);
        }
        else {
            throw Py::ValueError("action is 'move', 'press', 'release', 'click' or 'right_click'");
        }
        return Py::None();
    }

    Py::Object popupMenu(const Py::Tuple& args)
    {
        if (!PyArg_ParseTuple(args.ptr(), "")) {
            throw Py::Exception();
        }
        auto* menu = qobject_cast<QMenu*>(QApplication::activePopupWidget());
        if (!menu) {
            return Py::None();
        }
        Py::List items;
        for (QAction* action : menu->actions()) {
            if (!action->isSeparator() && action->isVisible()) {
                items.append(Py::String(action->text().remove(QLatin1Char('&')).toStdString()));
            }
        }
        return items;
    }

    Py::Object closePopups(const Py::Tuple& args)
    {
        if (!PyArg_ParseTuple(args.ptr(), "")) {
            throw Py::Exception();
        }
        int closed = 0;
        // A menu that refuses to close would stay the active popup: stop rather than loop forever.
        for (QWidget* popup = QApplication::activePopupWidget(); popup && closed < 16;
             popup = QApplication::activePopupWidget()) {
            if (!popup->close()) {
                break;
            }
            ++closed;
        }
        return Py::Long(closed);
    }

    Py::Object typeKeys(const Py::Tuple& args)
    {
        char* utf8 = nullptr;
        if (!PyArg_ParseTuple(args.ptr(), "s", &utf8)) {
            throw Py::Exception();
        }
        const QString text = QString::fromUtf8(utf8);
        for (qsizetype i = 0; i < text.size(); ++i) {
            int key = 0;
            QString typed;
            if (text[i] == QLatin1Char('{')) {
                const qsizetype end = text.indexOf(QLatin1Char('}'), i);
                if (end < 0) {
                    throw Py::ValueError("unclosed { in keys");
                }
                key = keyForName(text.mid(i + 1, end - i - 1));
                if (key == Qt::Key_Tab) {
                    typed = QStringLiteral("\t");
                }
                else if (key == Qt::Key_Return) {
                    typed = QStringLiteral("\r");
                }
                i = end;
            }
            else {
                key = keyForCharacter(text[i]);
                typed = text[i];
            }
            if (key == 0) {
                throw Py::ValueError("no key for " + text.mid(i, 1).toStdString());
            }
            QWidget* target = keyTarget();  // may change after each key, e.g. after Tab
            if (!target) {
                throw Py::RuntimeError("nothing has the keyboard focus");
            }
            QKeyEvent press(QEvent::KeyPress, key, Qt::NoModifier, typed);
            QApplication::sendEvent(target, &press);
            if ((target = keyTarget())) {
                QKeyEvent release(QEvent::KeyRelease, key, Qt::NoModifier, typed);
                QApplication::sendEvent(target, &release);
            }
            QApplication::processEvents();
        }
        return Py::None();
    }

    Py::Object startPicking(const Py::Tuple& args)
    {
        if (!PyArg_ParseTuple(args.ptr(), "")) {
            throw Py::Exception();
        }
        Gui::TaskView::TaskView* tasks = Gui::Control().taskPanel();
        if (tasks == nullptr) {
            return Py::False();
        }
        // FreeCAD's dress-up panels (TaskDressUpParameters) name their pick toggle buttonRefSel.
        for (QToolButton* button : tasks->findChildren<QToolButton*>(QStringLiteral("buttonRefSel"))) {
            if (button->isCheckable() && button->isEnabled() && !button->isChecked()) {
                button->setChecked(true);  // the panel's toggled slot starts picking
                return Py::True();
            }
        }
        return Py::False();
    }

    Py::Object selectionGate(const Py::Tuple& args)
    {
        if (!PyArg_ParseTuple(args.ptr(), "")) {
            throw Py::Exception();
        }
        return Py::Boolean(Gui::Selection().hasSelectionGate(nullptr));
    }

    Py::Object setDrawingMethod(const Py::Tuple& args)
    {
        int index = 0;
        if (!PyArg_ParseTuple(args.ptr(), "i", &index)) {
            throw Py::Exception();
        }
        Gui::TaskView::TaskView* tasks = Gui::Control().taskPanel();
        if (tasks == nullptr) {
            return Py::False();
        }
        for (QWidget* panel : tasks->findChildren<QWidget*>()) {
            // Sketcher's tool settings panel; its first list is the drawing method when a tool has several.
            if (qstrcmp(panel->metaObject()->className(), "SketcherGui::SketcherToolDefaultWidget") != 0) {
                continue;
            }
            auto* methods = panel->findChild<QComboBox*>(QStringLiteral("comboBox1"));
            if (methods == nullptr || !methods->isVisibleTo(panel)) {
                continue;
            }
            if (index < 0 || index >= methods->count()) {
                throw Py::ValueError(
                    "drawing method " + std::to_string(index) + " of " + std::to_string(methods->count())
                );
            }
            methods->setCurrentIndex(index);  // the tool follows its list (FreeCAD's controller)
            return Py::True();
        }
        return Py::False();
    }

    Py::Object setToolParameter(const Py::Tuple& args)
    {
        int number = 0;
        double value = 0.0;
        if (!PyArg_ParseTuple(args.ptr(), "id", &number, &value)) {
            throw Py::Exception();
        }
        static const char* const names[] = {"parameterOne", "parameterTwo",   "parameterThree", "parameterFour",
                                            "parameterFive", "parameterSix",  "parameterSeven", "parameterEight",
                                            "parameterNine", "parameterTen"};
        if (number < 1 || number > 10) {
            throw Py::ValueError("parameter number is 1 to 10");
        }
        Gui::TaskView::TaskView* tasks = Gui::Control().taskPanel();
        if (tasks == nullptr) {
            return Py::False();
        }
        for (QWidget* panel : tasks->findChildren<QWidget*>()) {
            if (qstrcmp(panel->metaObject()->className(), "SketcherGui::SketcherToolDefaultWidget") != 0) {
                continue;
            }
            auto* box = panel->findChild<Gui::QuantitySpinBox*>(QString::fromLatin1(names[number - 1]));
            if (box == nullptr || !box->isVisibleTo(panel)) {
                continue;
            }
            box->setValue(value);  // the tool follows its panel (FreeCAD's controller)
            return Py::True();
        }
        return Py::False();
    }

    Py::Object styleColor(const Py::Tuple& args)
    {
        char* name = nullptr;
        if (!PyArg_ParseTuple(args.ptr(), "s", &name)) {
            throw Py::Exception();
        }
        auto* manager = Base::provideService<Gui::StyleParameters::ParameterManager>();
        if (manager == nullptr || !manager->parameter(name)) {
            return Py::None();
        }
        // As FreeCAD's own users of a color token read it (e.g. Gui::LinearGizmo::updateColorTheme).
        const Gui::StyleParameters::ParameterDefinition<Base::Color> token {name, Base::Color(0.0F, 0.0F, 0.0F)};
        return Py::String(manager->resolve(token).asHexString());
    }

    Py::Object reloadStyleTokens(const Py::Tuple& args)
    {
        if (!PyArg_ParseTuple(args.ptr(), "")) {
            throw Py::Exception();
        }
        if (auto* manager = Base::provideService<Gui::StyleParameters::ParameterManager>()) {
            manager->reload();
        }
        return Py::None();
    }

    Py::Object tasksRoom(const Py::Tuple& args)
    {
        if (!PyArg_ParseTuple(args.ptr(), "")) {
            throw Py::Exception();
        }
        QMdiArea* area = Gui::getMainWindow()->getMdiArea();
        int height = area->geometry().height();
        if (auto* tabs = area->findChild<QTabBar*>()) {
            height -= tabs->height();  // as FreeCAD's OverlayManager counts it
        }
        return Py::TupleN(Py::Long(height), Py::Long(NaviCube::getNaviCubeSize()));
    }

    Py::Object followTasks(const Py::Tuple& args)
    {
        if (!PyArg_ParseTuple(args.ptr(), "")) {
            throw Py::Exception();
        }
        Gui::TaskView::TaskView* tasks = Gui::Control().taskPanel();
        if (tasks == nullptr) {
            return Py::False();
        }
        if (followedTasks != tasks) {
            followedTasks = tasks;
            QObject::connect(tasks, &Gui::TaskView::TaskView::taskUpdate, tasks, [tasks]() {
                QTimer::singleShot(0, tasks, [tasks]() {  // once the task view has finished changing
                    QWidget* focus = qApp->focusWidget();
                    if (tasks->isEmpty(false) && focus && (focus == tasks || tasks->isAncestorOf(focus))) {
                        if (QWidget* view = Gui::getMainWindow()->activeWindow()) {
                            view->setFocus(Qt::OtherFocusReason);
                        }
                        else {
                            focus->clearFocus();
                        }
                    }
                    Gui::OverlayManager::instance()->refresh();
                });
            });
        }
        return Py::True();
    }

    Py::Object tasksPanelRect(const Py::Tuple& args)
    {
        if (!PyArg_ParseTuple(args.ptr(), "")) {
            throw Py::Exception();
        }
        Gui::MainWindow* main = Gui::getMainWindow();
        auto* panel = main->findChild<QTabWidget*>(QStringLiteral("OverlayRight"));
        if (panel == nullptr || !panel->isVisible()) {
            return Py::None();
        }
        QPoint corner = panel->mapTo(main, QPoint(0, 0)) - main->getMdiArea()->mapTo(main, QPoint(0, 0));
        return Py::TupleN(
            Py::Long(corner.x()),
            Py::Long(corner.y()),
            Py::Long(panel->width()),
            Py::Long(panel->height())
        );
    }

    Py::Object focusField(const Py::Tuple& args)
    {
        char* name = nullptr;
        if (!PyArg_ParseTuple(args.ptr(), "s", &name)) {
            throw Py::Exception();
        }
        Gui::MainWindow* main = Gui::getMainWindow();
        for (QWidget* field : main->findChildren<QWidget*>(QString::fromUtf8(name))) {
            if (!inUse(field)) {
                continue;
            }
            if (auto* sizeBox = qobject_cast<Gui::QuantitySpinBox*>(field)) {
                sizeBox->selectNumber();
            }
            field->setFocus(Qt::OtherFocusReason);
            return Py::None();
        }
        throw Py::KeyError(std::string("no visible field named ") + name);
    }

    Py::Object setField(const Py::Tuple& args)
    {
        char* name = nullptr;
        double value = 0.0;
        if (!PyArg_ParseTuple(args.ptr(), "sd", &name, &value)) {
            throw Py::Exception();
        }
        Gui::MainWindow* main = Gui::getMainWindow();
        for (auto* box : main->findChildren<Gui::QuantitySpinBox*>(QString::fromUtf8(name))) {
            if (!inUse(box)) {
                continue;
            }
            box->setValue(value);  // in the box's unit's base (mm for a length); the panel follows it
            return Py::True();
        }
        return Py::False();
    }

    Py::Object focusWidget(const Py::Tuple& args)
    {
        if (!PyArg_ParseTuple(args.ptr(), "")) {
            throw Py::Exception();
        }
        QWidget* target = keyTarget();
        if (!target) {
            return Py::None();
        }
        auto* spinBox = qobject_cast<QAbstractSpinBox*>(target);
        QWidget* view = Gui::getMainWindow()->activeWindow();
        const bool inView = spinBox && view && dynamic_cast<Gui::View3DInventor*>(view)
            && view->isAncestorOf(target);
        Py::Tuple result(3);
        result.setItem(0, Py::String(target->metaObject()->className()));
        result.setItem(1, Py::Boolean(inView));
        result.setItem(2, Py::String(spinBox ? spinBox->text().toStdString() : std::string()));
        return result;
    }

    Py::Object addCommands(const Py::Tuple& args)
    {
        if (!PyArg_ParseTuple(args.ptr(), "")) {
            throw Py::Exception();
        }
        Gui::CommandManager& commands = Gui::Application::Instance->commandManager();
        if (!commands.getCommandByName("Studio_Construction")) {
            commands.addCommand(new ConstructionCommand());
            commands.addCommandMode("ToggleConstruction", "Studio_Construction");
        }
        return Py::None();
    }

    Py::Object constructionMode(const Py::Tuple& args)
    {
        if (!PyArg_ParseTuple(args.ptr(), "")) {
            throw Py::Exception();
        }
        return Py::Boolean(ConstructionCommand::on);
    }

    Py::Object watchConstruction(const Py::Tuple& args)
    {
        PyObject* callback = nullptr;
        if (!PyArg_ParseTuple(args.ptr(), "O", &callback)) {
            throw Py::Exception();
        }
        if (callback != Py_None && !PyCallable_Check(callback)) {
            throw Py::TypeError("callback must be callable or None");
        }
        Py_XDECREF(ConstructionCommand::listener);
        ConstructionCommand::listener = nullptr;
        if (callback != Py_None) {
            Py_INCREF(callback);
            ConstructionCommand::listener = callback;
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
