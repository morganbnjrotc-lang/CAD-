// SPDX-License-Identifier: LGPL-2.1-or-later

/***************************************************************************
 *   Copyright (c) 2022 Abdullah Tahiri <abdullah.tahiri.yo@gmail.com>     *
 *                                                                         *
 *   This file is part of the FreeCAD CAx development system.              *
 *                                                                         *
 *   This library is free software; you can redistribute it and/or         *
 *   modify it under the terms of the GNU Library General Public           *
 *   License as published by the Free Software Foundation; either          *
 *   version 2 of the License, or (at your option) any later version.      *
 *                                                                         *
 *   This library  is distributed in the hope that it will be useful,      *
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
 *   GNU Library General Public License for more details.                  *
 *                                                                         *
 *   You should have received a copy of the GNU Library General Public     *
 *   License along with this library; see the file COPYING.LIB. If not,    *
 *   write to the Free Software Foundation, Inc., 59 Temple Place,         *
 *   Suite 330, Boston, MA  02111-1307, USA                                *
 *                                                                         *
 ***************************************************************************/


#pragma once

#include <QApplication>

#include <Gui/BitmapFactory.h>
#include <Gui/Notifications.h>
#include <Gui/Command.h>
#include <Gui/CommandT.h>
#include <Gui/InputHint.h>

#include <Mod/Sketcher/App/SketchObject.h>

#include "Utils.h"

#include "DrawSketchDefaultWidgetController.h"
#include "DrawSketchControllableHandler.h"

#include "SketcherRegularPolygonDialog.h"

namespace SketcherGui
{

class DrawSketchHandlerPolygon;

namespace ConstructionMethods
{

enum class PolygonConstructionMethod
{
    Inscribed,      // the center, then a corner
    Circumscribed,  // the center, then the middle of a side
    Edge,           // two corners of one side; the polygon on the left going from the first
    End             // Must be the last one
};

}  // namespace ConstructionMethods

using DSHPolygonController = DrawSketchDefaultWidgetController<
    DrawSketchHandlerPolygon,
    StateMachines::TwoSeekEnd,
    /*PAutoConstraintSize =*/2,
    /*OnViewParametersT =*/OnViewParameters<4, 4, 4>,
    /*WidgetParametersT =*/WidgetParameters<1, 1, 1>,
    /*WidgetCheckboxesT =*/WidgetCheckboxes<0, 0, 0>,
    /*WidgetComboboxesT =*/WidgetComboboxes<1, 1, 1>,
    /*WidgetLineEditsT =*/WidgetLineEdits<0, 0, 0>,
    ConstructionMethods::PolygonConstructionMethod,
    /*bool PFirstComboboxIsConstructionMethod =*/true>;

using DSHPolygonControllerBase = DSHPolygonController::ControllerBase;

using DrawSketchHandlerPolygonBase = DrawSketchControllableHandler<DSHPolygonController>;


class DrawSketchHandlerPolygon: public DrawSketchHandlerPolygonBase
{
    Q_DECLARE_TR_FUNCTIONS(SketcherGui::DrawSketchHandlerPolygon)

    friend DSHPolygonController;
    friend DSHPolygonControllerBase;

public:
    explicit DrawSketchHandlerPolygon(int corners = 6)  // NOLINT
        : numberOfCorners(corners)
        , radius(0.0)
    {}
    ~DrawSketchHandlerPolygon() override = default;

private:
    void updateDataAndDrawToPosition(Base::Vector2d onSketchPos) override
    {
        switch (state()) {
            case SelectMode::SeekFirst: {
                toolWidgetManager.drawPositionAtCursor(onSketchPos);

                firstClick = onSketchPos;
                centerPoint = onSketchPos;

                seekAndRenderAutoConstraint(sugConstraints[0], onSketchPos, Base::Vector2d(0.f, 0.f));
            } break;
            case SelectMode::SeekSecond: {
                toolWidgetManager.drawDirectionAtCursor(onSketchPos, firstClick);

                secondClick = onSketchPos;
                placeCorners();

                CreateAndDrawShapeGeometry();

                seekAndRenderAutoConstraint(sugConstraints[1], onSketchPos, Base::Vector2d(0.f, 0.f));
            } break;
            default:
                break;
        }
    }

    void executeCommands() override
    {
        unsetCursor();
        resetPositionText();
        openCommand(QT_TRANSLATE_NOOP("Command", "Add polygon"));

        try {
            Gui::Command::doCommand(
                Gui::Command::Doc,
                "import ProfileLib.RegularPolygon\n"
                "ProfileLib.RegularPolygon.makeRegularPolygon(%s,%i,App.Vector("
                "%f,%f,0),App.Vector(%f,%f,0),%s)",
                Gui::Command::getObjectCmd(sketchgui->getObject()).c_str(),
                numberOfCorners,
                centerPoint.x,
                centerPoint.y,
                firstCorner.x,
                firstCorner.y,
                constructionModeAsBooleanText()
            );

            if (constructionMethod() == ConstructionMethod::Circumscribed) {
                // The circle touching the sides, which a typed size sets: concentric with the
                // corners' circle and touching the side through the second click (the first side).
                // Touching every side would be redundant, and without the corners' circle an even
                // number of equal sides touching a circle could still lean like a rhombus.
                int outer = getHighestCurveIndex();
                int firstSide = outer - static_cast<int>(numberOfCorners);
                Gui::cmdAppObjectArgs(
                    sketchgui->getObject(),
                    "addGeometry(Part.Circle(App.Vector(%f,%f,0),App.Vector(0,0,1),%f),True)",
                    centerPoint.x,
                    centerPoint.y,
                    (secondClick - firstClick).Length()
                );
                Gui::cmdAppObjectArgs(
                    sketchgui->getObject(),
                    "addConstraint(Sketcher.Constraint('Coincident',%d,3,%d,3))",
                    outer + 1,
                    outer
                );
                Gui::cmdAppObjectArgs(
                    sketchgui->getObject(),
                    "addConstraint(Sketcher.Constraint('Tangent',%d,%d))",
                    outer + 1,
                    firstSide
                );
            }

            commitCommand();

            tryAutoRecomputeIfNotSolve(sketchgui->getObject<Sketcher::SketchObject>());
        }
        catch (const Base::Exception&) {
            Gui::NotifyError(
                sketchgui,
                QT_TRANSLATE_NOOP("Notifications", "Error"),
                QT_TRANSLATE_NOOP("Notifications", "Failed to add polygon")
            );

            abortCommand();
            THROWM(
                Base::RuntimeError,
                QT_TRANSLATE_NOOP(
                    "Notifications",
                    "Tool execution aborted"
                ) "\n"
            )  // This prevents constraints from being
               // applied on non existing geometry
        }
    }

    void generateAutoConstraints() override
    {
        if (constructionMethod() == ConstructionMethod::Edge) {
            // the two clicks are the first side's ends
            const int firstsidegeoid = cornersCircleGeoId() - static_cast<int>(numberOfCorners);
            generateAutoConstraintsOnElement(
                sugConstraints[0],
                firstsidegeoid,
                Sketcher::PointPos::start
            );
            generateAutoConstraintsOnElement(sugConstraints[1], firstsidegeoid, Sketcher::PointPos::end);
            removeRedundantAutoConstraints();
            return;
        }

        // add auto constraints at the center of the polygon
        auto* obj = sketchgui->getObject<Sketcher::SketchObject>();
        for (int geoId = cornersCircleGeoId(); geoId >= 0; geoId--) {
            const Part::Geometry* geo = obj->getGeometry(geoId);
            if (geo->is<Part::GeomCircle>()) {
                int circlegeoid = geoId;
                int lastsidegeoid = geoId - 1;
                if (sugConstraints[0].size() > 0) {
                    generateAutoConstraintsOnElement(
                        sugConstraints[0],
                        circlegeoid,
                        Sketcher::PointPos::mid
                    );
                }

                // add auto constraints to the last side of the polygon (Circumscribed: the second
                // click is the middle of a side, no corner to attach them to)
                if (sugConstraints[1].size() > 0
                    && constructionMethod() == ConstructionMethod::Inscribed) {
                    generateAutoConstraintsOnElement(
                        sugConstraints[1],
                        lastsidegeoid,
                        Sketcher::PointPos::end
                    );
                }

                // Ensure temporary autoconstraints do not generate a redundancy and that the
                // geometry parameters are accurate This is particularly important for adding widget
                // mandated constraints.
                removeRedundantAutoConstraints();
                return;
            }
        }
    }

    /// The construction circle through the corners, once added (the circle touching the sides
    /// comes after it for Circumscribed).
    int cornersCircleGeoId()
    {
        return getHighestCurveIndex()
            - (constructionMethod() == ConstructionMethod::Circumscribed ? 1 : 0);
    }

    void createAutoConstraints() override
    {
        createGeneratedAutoConstraints(true);

        sugConstraints[0].clear();
        sugConstraints[1].clear();
    }

    std::string getToolName() const override
    {
        return "DSH_Polygon";
    }

    QString getCrosshairCursorSVGName() const override
    {
        return QStringLiteral("Sketcher_Pointer_Regular_Polygon");
    }

    std::unique_ptr<QWidget> createWidget() const override
    {
        return std::make_unique<SketcherToolDefaultWidget>();
    }

    bool isWidgetVisible() const override
    {
        return true;
    };

    QPixmap getToolIcon() const override
    {
        return Gui::BitmapFactory().pixmap("Sketcher_CreateRegularPolygon");
    }

    QString getToolWidgetText() const override
    {
        return QString(tr("Polygon Parameters"));
    }

    bool canGoToNextMode() override
    {
        if (state() == SelectMode::SeekSecond && radius < Precision::Confusion()) {
            // Prevent validation of null shape.
            return false;
        }

        return true;
    }

    void angleSnappingControl() override
    {
        if (state() == SelectMode::SeekSecond) {
            setAngleSnapping(true, firstClick);
        }

        else {
            setAngleSnapping(false);
        }
    }

private:
    unsigned int numberOfCorners;
    Base::Vector2d centerPoint, firstCorner;
    Base::Vector2d firstClick, secondClick;
    double radius;

    /// The center and the first corner (where ProfileLib's polygon starts, going counterclockwise)
    /// from the two clicks.
    void placeCorners()
    {
        const double half = std::numbers::pi / static_cast<double>(numberOfCorners);
        switch (constructionMethod()) {
            case ConstructionMethod::Inscribed:
                centerPoint = firstClick;
                firstCorner = secondClick;
                break;
            case ConstructionMethod::Circumscribed: {
                // the second click is the middle of the first side: its corners half a step either
                // side, 1 / cos(half) farther out
                centerPoint = firstClick;
                const Base::Vector2d apothem = secondClick - firstClick;
                const double c = cos(half);
                const double s = sin(half);
                const Base::Vector2d back(c * apothem.x + s * apothem.y, -s * apothem.x + c * apothem.y);
                firstCorner = centerPoint + back / c;
            } break;
            case ConstructionMethod::Edge: {
                const Base::Vector2d side = secondClick - firstClick;
                const double length = side.Length();
                firstCorner = firstClick;
                if (length < Precision::Confusion()) {
                    centerPoint = firstClick;  // no polygon yet
                    break;
                }
                const Base::Vector2d left(-side.y / length, side.x / length);
                centerPoint = (firstClick + secondClick) / 2 + (length / (2 * tan(half))) * left;
            } break;
            default:
                break;
        }
    }

    void createShape(bool onlyeditoutline) override
    {
        Q_UNUSED(onlyeditoutline)

        ShapeGeometry.clear();

        Base::Vector2d prevCorner = firstCorner;
        Base::Vector2d dV = firstCorner - centerPoint;
        radius = dV.Length();

        if (radius < Precision::Confusion()) {
            return;
        }

        double angleOfSeparation = 2.0 * std::numbers::pi
            / static_cast<double>(numberOfCorners);  // NOLINT
        double cos_v = cos(angleOfSeparation);
        double sin_v = sin(angleOfSeparation);

        double rx = dV.x;
        double ry = dV.y;

        for (int i = 1; i <= static_cast<int>(numberOfCorners); i++) {
            const double old_rx = rx;
            rx = cos_v * rx - sin_v * ry;
            ry = cos_v * ry + sin_v * old_rx;
            Base::Vector2d newCorner = Base::Vector2d(centerPoint.x + rx, centerPoint.y + ry);
            addLineToShapeGeometry(toVector3d(prevCorner), toVector3d(newCorner), isConstructionMode());
            prevCorner = newCorner;
        }
    }

    std::list<Gui::InputHint> getToolHints() const override
    {
        using enum Gui::InputHint::UserInput;
        using State = std::pair<ConstructionMethod, SelectMode>;

        const Gui::InputHint sidesHint {tr("%1/%2 increase/decrease number of sides"), {KeyU, KeyJ}};
        const Gui::InputHint switchModeHint {tr("%1 switch mode"), {KeyM}};

        return Gui::lookupHints<State>(
            {constructionMethod(), state()},
            {
                {.state = {ConstructionMethod::Inscribed, SelectMode::SeekFirst},
                 .hints =
                     {
                         {tr("%1 pick polygon center"), {MouseLeft}},
                         sidesHint,
                         switchModeHint,
                     }},
                {.state = {ConstructionMethod::Inscribed, SelectMode::SeekSecond},
                 .hints =
                     {
                         {tr("%1 pick rotation and size"), {MouseMove}},
                         {tr("%1 confirm"), {MouseLeft}},
                         sidesHint,
                     }},
                {.state = {ConstructionMethod::Circumscribed, SelectMode::SeekFirst},
                 .hints =
                     {
                         {tr("%1 pick polygon center"), {MouseLeft}},
                         sidesHint,
                         switchModeHint,
                     }},
                {.state = {ConstructionMethod::Circumscribed, SelectMode::SeekSecond},
                 .hints =
                     {
                         {tr("%1 pick the middle of a side"), {MouseLeft}},
                         sidesHint,
                     }},
                {.state = {ConstructionMethod::Edge, SelectMode::SeekFirst},
                 .hints =
                     {
                         {tr("%1 pick the first corner of a side"), {MouseLeft}},
                         sidesHint,
                         switchModeHint,
                     }},
                {.state = {ConstructionMethod::Edge, SelectMode::SeekSecond},
                 .hints =
                     {
                         {tr("%1 pick the next corner (the polygon goes on the left)"), {MouseLeft}},
                         sidesHint,
                     }},
            });
    }
};

template<>
auto DSHPolygonControllerBase::getState(int labelindex) const
{
    switch (labelindex) {
        case OnViewParameter::First:
        case OnViewParameter::Second:
            return SelectMode::SeekFirst;
            break;
        case OnViewParameter::Third:
        case OnViewParameter::Fourth:
            return SelectMode::SeekSecond;
            break;
        default:
            THROWM(Base::ValueError, "OnViewParameter index without an associated machine state")
    }
}

template<>
void DSHPolygonController::firstKeyShortcut()
{
    auto value = toolWidget->getParameter(WParameter::First);
    toolWidget->setParameterWithoutPassingFocus(WParameter::First, value + 1);
}

template<>
void DSHPolygonController::secondKeyShortcut()
{
    auto value = toolWidget->getParameter(WParameter::First);
    if (value > 3.0) {  // NOLINT
        toolWidget->setParameterWithoutPassingFocus(WParameter::First, value - 1);
    }
}

template<>
void DSHPolygonController::configureToolWidget()
{
    if (!init) {  // Code to be executed only upon initialisation
        QStringList names = {
            QApplication::translate("Sketcher_CreateRegularPolygon", "Inscribed (center, corner)"),
            QApplication::translate("Sketcher_CreateRegularPolygon", "Circumscribed (center, middle of a side)"),
            QApplication::translate("Sketcher_CreateRegularPolygon", "Edge (two corners)")
        };
        toolWidget->setComboboxElements(WCombobox::FirstCombo, names);
        for (int i = 0; i < names.size(); ++i) {
            toolWidget->setComboboxItemIcon(
                WCombobox::FirstCombo,
                i,
                Gui::BitmapFactory().iconFromTheme(
                    handler->isConstructionMode() ? "Sketcher_CreateRegularPolygon_Constr"
                                                  : "Sketcher_CreateRegularPolygon"
                )
            );
        }
    }

    toolWidget->setParameterLabel(
        WParameter::First,
        QApplication::translate("ToolWidgetManager_p4", "Sides")
    );
    toolWidget->setParameter(WParameter::First,
                             handler->numberOfCorners);  // unconditionally set
    toolWidget->configureParameterUnit(WParameter::First, Base::Unit());
    toolWidget->configureParameterMin(WParameter::First, 3.0);  // NOLINT
    // We set a reasonable max to avoid the spinbox from being very large
    toolWidget->configureParameterMax(WParameter::First, 9999.0);  // NOLINT
    toolWidget->configureParameterDecimals(WParameter::First, 0);

    onViewParameters[OnViewParameter::First]->setLabelType(Gui::SoDatumLabel::DISTANCEX);
    onViewParameters[OnViewParameter::Second]->setLabelType(Gui::SoDatumLabel::DISTANCEY);
    onViewParameters[OnViewParameter::Third]->setLabelType(
        Gui::SoDatumLabel::DISTANCE,
        Gui::EditableDatumLabel::Function::Dimensioning
    );
    onViewParameters[OnViewParameter::Fourth]->setLabelType(
        Gui::SoDatumLabel::ANGLE,
        Gui::EditableDatumLabel::Function::Dimensioning
    );
}

template<>
void DSHPolygonController::adaptDrawingToParameterChange(int parameterindex, double value)
{
    switch (parameterindex) {
        case WParameter::First:
            handler->numberOfCorners = std::max(3, static_cast<int>(value));
            break;
    }
}

template<>
void DSHPolygonControllerBase::doEnforceControlParameters(Base::Vector2d& onSketchPos)
{
    switch (handler->state()) {
        case SelectMode::SeekFirst: {
            auto& firstParam = onViewParameters[OnViewParameter::First];
            auto& secondParam = onViewParameters[OnViewParameter::Second];

            if (firstParam->isSet) {
                onSketchPos.x = firstParam->getValue();
            }

            if (secondParam->isSet) {
                onSketchPos.y = secondParam->getValue();
            }
        } break;
        case SelectMode::SeekSecond: {
            auto& thirdParam = onViewParameters[OnViewParameter::Third];
            auto& fourthParam = onViewParameters[OnViewParameter::Fourth];

            // Sizes measure from the first click: the center to a corner (Inscribed) or to the
            // middle of a side (Circumscribed); one side (Edge).
            const Base::Vector2d anchor = handler->firstClick;
            Base::Vector2d dir = onSketchPos - anchor;
            if (dir.Length() < Precision::Confusion()) {
                dir.x = 1.0;  // if direction null, default to (1,0)
            }
            double length = dir.Length();

            if (thirdParam->isSet) {
                length = thirdParam->getValue();
                if (length < Precision::Confusion() && thirdParam->hasFinishedEditing) {
                    unsetOnViewParameter(thirdParam.get());
                    return;
                }

                onSketchPos = anchor + length * dir.Normalize();
            }

            if (fourthParam->isSet) {
                double angle = Base::toRadians(fourthParam->getValue());
                onSketchPos.x = anchor.x + cos(angle) * length;
                onSketchPos.y = anchor.y + sin(angle) * length;
            }
        } break;
        default:
            break;
    }
}

template<>
void DSHPolygonController::adaptParameters(Base::Vector2d onSketchPos)
{
    switch (handler->state()) {
        case SelectMode::SeekFirst: {
            auto& firstParam = onViewParameters[OnViewParameter::First];
            auto& secondParam = onViewParameters[OnViewParameter::Second];

            if (!firstParam->isSet) {
                setOnViewParameterValue(OnViewParameter::First, onSketchPos.x);
            }

            if (!secondParam->isSet) {
                setOnViewParameterValue(OnViewParameter::Second, onSketchPos.y);
            }

            bool sameSign = onSketchPos.x * onSketchPos.y > 0.;
            firstParam->setLabelAutoDistanceReverse(!sameSign);
            secondParam->setLabelAutoDistanceReverse(sameSign);
            firstParam->setPoints(Base::Vector3d(), toVector3d(onSketchPos));
            secondParam->setPoints(Base::Vector3d(), toVector3d(onSketchPos));
        } break;
        case SelectMode::SeekSecond: {
            auto& thirdParam = onViewParameters[OnViewParameter::Third];
            auto& fourthParam = onViewParameters[OnViewParameter::Fourth];

            // between the clicks: Inscribed's center and corner, as before
            Base::Vector3d start = toVector3d(handler->firstClick);
            Base::Vector3d end = toVector3d(handler->secondClick);
            Base::Vector3d vec = end - start;

            if (!thirdParam->isSet) {
                setOnViewParameterValue(OnViewParameter::Third, vec.Length());
            }

            double range = (handler->secondClick - handler->firstClick).Angle();
            if (!fourthParam->isSet) {
                setOnViewParameterValue(
                    OnViewParameter::Fourth,
                    Base::toDegrees(range),
                    Base::Unit::Angle
                );
            }

            thirdParam->setPoints(start, end);
            fourthParam->setPoints(start, Base::Vector3d());
            fourthParam->setLabelRange(range);

        } break;
        default:
            break;
    }
}

template<>
void DSHPolygonController::computeNextDrawSketchHandlerMode()
{
    switch (handler->state()) {
        case SelectMode::SeekFirst: {
            auto& firstParam = onViewParameters[OnViewParameter::First];
            auto& secondParam = onViewParameters[OnViewParameter::Second];

            if (firstParam->hasFinishedEditing && secondParam->hasFinishedEditing) {
                handler->setNextState(SelectMode::SeekSecond);
            }
        } break;
        case SelectMode::SeekSecond: {
            auto& thirdParam = onViewParameters[OnViewParameter::Third];
            auto& fourthParam = onViewParameters[OnViewParameter::Fourth];

            if (thirdParam->hasFinishedEditing && fourthParam->hasFinishedEditing) {
                handler->setNextState(SelectMode::End);
            }
        } break;
        default:
            break;
    }
}

template<>
void DSHPolygonController::addConstraints()
{
    App::DocumentObject* obj = handler->sketchgui->getObject();

    int lastCurve = handler->getHighestCurveIndex();

    auto x0 = onViewParameters[OnViewParameter::First]->getValue();
    auto y0 = onViewParameters[OnViewParameter::Second]->getValue();
    auto radius = onViewParameters[OnViewParameter::Third]->getValue();
    auto angle = Base::toRadians(onViewParameters[OnViewParameter::Fourth]->getValue());

    auto x0set = onViewParameters[OnViewParameter::First]->isSet;
    auto y0set = onViewParameters[OnViewParameter::Second]->isSet;
    auto radiusSet = onViewParameters[OnViewParameter::Third]->isSet;
    auto angleSet = onViewParameters[OnViewParameter::Fourth]->isSet;

    using namespace Sketcher;

    if (handler->constructionMethod() != DrawSketchHandlerPolygon::ConstructionMethod::Inscribed) {
        // Circumscribed: the typed position is the center, the size the circle touching the sides,
        // the angle the direction to the middle of the first side (which is square to it).
        // Edge: the typed position is the first corner, the size and angle the first side's.
        const bool edge = handler->constructionMethod()
            == DrawSketchHandlerPolygon::ConstructionMethod::Edge;
        const int corners = edge ? lastCurve : lastCurve - 1;  // the corners' circle
        const int firstSide = corners - static_cast<int>(handler->numberOfCorners);
        const GeoElementId position = edge ? GeoElementId(firstSide, PointPos::start)
                                           : GeoElementId(corners, PointPos::mid);
        const double sideAngle = edge ? angle : angle + std::numbers::pi / 2;

        auto size = [&]() {
            if (edge) {
                Gui::cmdAppObjectArgs(obj, "addConstraint(Sketcher.Constraint('Distance',%d,%f)) ", firstSide, radius);
            }
            else {
                Gui::cmdAppObjectArgs(obj, "addConstraint(Sketcher.Constraint('Radius',%d,%f)) ", lastCurve, radius);
            }
        };

        if (handler->AutoConstraints.empty()) {
            if (x0set) {
                ConstraintToAttachment(position, GeoElementId::VAxis, x0, obj);
            }
            if (y0set) {
                ConstraintToAttachment(position, GeoElementId::HAxis, y0, obj);
            }
            if (radiusSet) {
                size();
            }
            if (angleSet) {
                ConstraintLineByAngle(firstSide, sideAngle, obj);
            }
            return;
        }

        auto pointinfo = handler->getPointInfo(position);
        if (x0set && pointinfo.isXDoF()) {
            ConstraintToAttachment(position, GeoElementId::VAxis, x0, obj);
            handler->diagnoseWithAutoConstraints();
            pointinfo = handler->getPointInfo(position);
        }
        if (y0set && pointinfo.isYDoF()) {
            ConstraintToAttachment(position, GeoElementId::HAxis, y0, obj);
            handler->diagnoseWithAutoConstraints();
        }
        int DoFs = handler->getLineDoFs(firstSide);
        if (radiusSet && DoFs > 0) {
            size();
            handler->diagnoseWithAutoConstraints();
            DoFs = handler->getLineDoFs(firstSide);
        }
        if (angleSet && DoFs > 0) {
            ConstraintLineByAngle(firstSide, sideAngle, obj);
        }
        return;
    }

    auto constraintx0 = [&]() {
        ConstraintToAttachment(GeoElementId(lastCurve, PointPos::mid), GeoElementId::VAxis, x0, obj);
    };

    auto constrainty0 = [&]() {
        ConstraintToAttachment(GeoElementId(lastCurve, PointPos::mid), GeoElementId::HAxis, y0, obj);
    };

    auto constraintradius = [&]() {
        Gui::cmdAppObjectArgs(obj, "addConstraint(Sketcher.Constraint('Radius',%d,%f)) ", lastCurve, radius);
    };

    auto constraintAngle = [&]() {
        int circleGeoId = lastCurve;
        int lastSideGeoId = lastCurve - 1;

        using std::numbers::pi;
        // for horizontal/vertical angles add according constraint instead of angle constraint
        if (fabs(std::remainder(angle, pi)) < Precision::Confusion()) {
            Gui::cmdAppObjectArgs(
                obj,
                "addConstraint(Sketcher.Constraint('Horizontal',%d,%d,%d,%d)) ",
                circleGeoId,
                static_cast<int>(PointPos::mid),
                lastSideGeoId,
                static_cast<int>(PointPos::end)
            );
        }
        else if (fabs(std::remainder(angle, pi / 2)) < Precision::Confusion()) {
            Gui::cmdAppObjectArgs(
                obj,
                "addConstraint(Sketcher.Constraint('Vertical',%d,%d,%d,%d)) ",
                circleGeoId,
                static_cast<int>(PointPos::mid),
                lastSideGeoId,
                static_cast<int>(PointPos::end)
            );
        }
        else {
            Gui::cmdAppObjectArgs(
                obj,
                "addGeometry(Part.LineSegment(App.Vector(%f,%f,0),App.Vector(%f,%f,0)),True)",
                handler->centerPoint.x,
                handler->centerPoint.y,
                handler->firstCorner.x,
                handler->firstCorner.y
            );

            int radialGeoId = handler->getHighestCurveIndex();
            Gui::cmdAppObjectArgs(
                obj,
                "addConstraint(Sketcher.Constraint('Coincident',%d,%d,%d,%d))",
                radialGeoId,
                static_cast<int>(PointPos::start),
                circleGeoId,
                static_cast<int>(PointPos::mid)
            );
            Gui::cmdAppObjectArgs(
                obj,
                "addConstraint(Sketcher.Constraint('Coincident',%d,%d,%d,%d))",
                radialGeoId,
                static_cast<int>(PointPos::end),
                lastSideGeoId,
                static_cast<int>(PointPos::end)
            );

            Gui::cmdAppObjectArgs(
                obj,
                "addConstraint(Sketcher.Constraint('Angle',%d,%f))",
                radialGeoId,
                angle
            );
        }
    };

    // NOTE: if AutoConstraints is empty, we can add constraints directly without any diagnose. No
    // diagnose was run.
    if (handler->AutoConstraints.empty()) {
        if (x0set) {
            constraintx0();
        }

        if (y0set) {
            constrainty0();
        }

        if (radiusSet) {
            constraintradius();
        }

        if (angleSet) {
            constraintAngle();
        }
    }
    else {  // There is a valid diagnose.
        auto startpointinfo = handler->getPointInfo(GeoElementId(lastCurve, PointPos::mid));

        // if Autoconstraints is empty we do not have a diagnosed system and the parameter will
        // always be set
        if (x0set && startpointinfo.isXDoF()) {
            constraintx0();

            handler->diagnoseWithAutoConstraints();  // ensure we have recalculated parameters after
                                                     // each constraint addition

            startpointinfo = handler->getPointInfo(
                GeoElementId(lastCurve, PointPos::mid)
            );  // get updated point position
        }

        // if Autoconstraints is empty we do not have a diagnosed system and the parameter will
        // always be set
        if (y0set && startpointinfo.isYDoF()) {
            constrainty0();

            handler->diagnoseWithAutoConstraints();  // ensure we have recalculated parameters after
                                                     // each constraint addition
        }

        auto edgeinfo = handler->getEdgeInfo(lastCurve);
        auto circle = static_cast<SolverGeometryExtension::Circle&>(edgeinfo);

        // if Autoconstraints is empty we do not have a diagnosed system and the parameter will
        // always be set
        if (radiusSet && circle.isRadiusDoF()) {
            constraintradius();
        }

        if (angleSet) {
            constraintAngle();
        }
    }
}

}  // namespace SketcherGui
