// SPDX-License-Identifier: LGPL-2.1-or-later

/***************************************************************************
 *   Copyright (c) 2023 Ondsel <development@ondsel.com>                    *
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

#include "DrawSketchDefaultWidgetController.h"
#include "DrawSketchControllableHandler.h"

#include "Utils.h"

namespace SketcherGui
{

class DrawSketchHandlerArcSlot;

namespace ConstructionMethods
{

enum class ArcSlotConstructionMethod
{
    ArcSlot,
    RectangleSlot,
    ThreePoint,  // the ends' centers, a point the slot's middle passes through, the width (Fusion's)
    End          // Must be the last one
};

}  // namespace ConstructionMethods

using DSHArcSlotController = DrawSketchDefaultWidgetController<
    DrawSketchHandlerArcSlot,
    StateMachines::FourSeekEnd,
    /*PAutoConstraintSize =*/3,                     // NOLINT
    /*OnViewParametersT =*/OnViewParameters<6, 6, 6>,  // NOLINT
    /*WidgetParametersT =*/WidgetParameters<0, 0, 0>,  // NOLINT
    /*WidgetCheckboxesT =*/WidgetCheckboxes<0, 0, 0>,  // NOLINT
    /*WidgetComboboxesT =*/WidgetComboboxes<1, 1, 1>,  // NOLINT
    /*WidgetLineEditsT =*/WidgetLineEdits<0, 0, 0>,
    ConstructionMethods::ArcSlotConstructionMethod,
    /*bool PFirstComboboxIsConstructionMethod =*/true>;

using DSHArcSlotControllerBase = DSHArcSlotController::ControllerBase;

using DrawSketchHandlerArcSlotBase = DrawSketchControllableHandler<DSHArcSlotController>;

class DrawSketchHandlerArcSlot: public DrawSketchHandlerArcSlotBase
{
    Q_DECLARE_TR_FUNCTIONS(SketcherGui::DrawSketchHandlerArcSlot)

    friend DSHArcSlotController;
    friend DSHArcSlotControllerBase;

public:
    explicit DrawSketchHandlerArcSlot(ConstructionMethod constrMethod = ConstructionMethod::ArcSlot)
        : DrawSketchHandlerArcSlotBase(constrMethod)
        , startAngle(0.)
        , startAngleBackup(0.)
        , endAngle(0.)
        , arcAngle(0.)
        , r(0.)
        , radius(0.)
        , angleReversed(false)
    {}

    ~DrawSketchHandlerArcSlot() override = default;

    std::list<Gui::InputHint> getToolHints() const override
    {
        using enum Gui::InputHint::UserInput;

        const Gui::InputHint switchModeHint {.message = tr("%1 switch mode"), .sequences = {KeyM}};

        if (constructionMethod() == ConstructionMethod::ThreePoint) {
            return Gui::lookupHints<SelectMode>(
                state(),
                {
                    {.state = SelectMode::SeekFirst,
                     .hints = {{tr("%1 pick slot start"), {MouseLeft}}, switchModeHint}},
                    {.state = SelectMode::SeekSecond,
                     .hints = {{tr("%1 pick slot end"), {MouseLeft}}, switchModeHint}},
                    {.state = SelectMode::SeekThird,
                     .hints = {{tr("%1 pick a point the slot passes through"), {MouseLeft}}, switchModeHint}},
                    {.state = SelectMode::SeekFourth,
                     .hints = {{tr("%1 pick slot width"), {MouseLeft}}, switchModeHint}},
                }
            );
        }

        return Gui::lookupHints<SelectMode>(state(),
                                            {
                                                {.state = SelectMode::SeekFirst,
                                                 .hints =
                                                     {
                                                         {tr("%1 pick slot center"), {MouseLeft}},
                                                         switchModeHint,
                                                     }},
                                                {.state = SelectMode::SeekSecond,
                                                 .hints =
                                                     {
                                                         {tr("%1 pick slot radius"), {MouseLeft}},
                                                         switchModeHint,
                                                     }},
                                                {.state = SelectMode::SeekThird,
                                                 .hints =
                                                     {
                                                         {tr("%1 pick slot angle"), {MouseLeft}},
                                                         switchModeHint,
                                                     }},
                                                {.state = SelectMode::SeekFourth,
                                                 .hints =
                                                     {
                                                         {tr("%1 pick slot width"), {MouseLeft}},
                                                         switchModeHint,
                                                     }},
                                            });
    }

private:
    void updateDataAndDrawToPosition(Base::Vector2d onSketchPos) override
    {
        if (constructionMethod() == ConstructionMethod::ThreePoint) {
            updateThreePoint(onSketchPos);
            return;
        }
        switch (state()) {
            case SelectMode::SeekFirst: {
                toolWidgetManager.drawPositionAtCursor(onSketchPos);

                centerPoint = onSketchPos;

                seekAndRenderAutoConstraint(sugConstraints[0], onSketchPos, Base::Vector2d(0.f, 0.f));
            } break;
            case SelectMode::SeekSecond: {
                toolWidgetManager.drawDirectionAtCursor(onSketchPos, centerPoint);

                startPoint = onSketchPos;
                startAngle = (startPoint - centerPoint).Angle();
                startAngleBackup = startAngle;
                radius = (startPoint - centerPoint).Length();

                CreateAndDrawShapeGeometry();

                seekAndRenderAutoConstraint(sugConstraints[1], onSketchPos, Base::Vector2d(0.f, 0.f));
            } break;
            case SelectMode::SeekThird: {
                endPoint = centerPoint + (onSketchPos - centerPoint).Normalize() * radius;
                if (constructionMethod() == DrawSketchHandlerArcSlot::ConstructionMethod::ArcSlot) {
                    const double scale = 10;
                    r = radius / scale;
                }
                else {
                    const double scale = 1.2;
                    r = radius * scale;
                }

                startAngle = startAngleBackup;

                double angle1 = (onSketchPos - centerPoint).Angle() - startAngle;
                double angle2 = angle1 + (angle1 < 0. ? 2 : -2) * std::numbers::pi;
                arcAngle = abs(angle1 - arcAngle) < abs(angle2 - arcAngle) ? angle1 : angle2;

                reverseIfNecessary();

                CreateAndDrawShapeGeometry();

                toolWidgetManager.drawDoubleAtCursor(onSketchPos, arcAngle, Base::Unit::Angle);

                seekAndRenderAutoConstraint(sugConstraints[2], onSketchPos, Base::Vector2d(0.0, 0.0));
            } break;
            case SelectMode::SeekFourth: {

                if (constructionMethod() == DrawSketchHandlerArcSlot::ConstructionMethod::ArcSlot) {
                    r = std::min(radius, fabs(radius - (onSketchPos - centerPoint).Length()));
                }
                else {
                    r = (onSketchPos - centerPoint).Length();
                }

                toolWidgetManager.drawDoubleAtCursor(onSketchPos, r);

                CreateAndDrawShapeGeometry();
            } break;
            default:
                break;
        }
    }

    /// Three Point: the start end's center, the far end's center, a point the slot's middle passes
    /// through (the arc around the slot's center goes through all three), the width.
    void updateThreePoint(Base::Vector2d onSketchPos)
    {
        switch (state()) {
            case SelectMode::SeekFirst: {
                toolWidgetManager.drawPositionAtCursor(onSketchPos);
                startPoint = onSketchPos;
                seekAndRenderAutoConstraint(sugConstraints[0], onSketchPos, Base::Vector2d(0.f, 0.f));
            } break;
            case SelectMode::SeekSecond: {
                toolWidgetManager.drawPositionAtCursor(onSketchPos);
                endPoint = onSketchPos;
                CreateAndDrawShapeGeometry();
                seekAndRenderAutoConstraint(sugConstraints[1], onSketchPos, Base::Vector2d(0.f, 0.f));
            } break;
            case SelectMode::SeekThird: {
                if (!arcThroughThreePoints(onSketchPos)) {
                    radius = 0.;  // in a line with the ends: no arc, nothing drawn
                    CreateAndDrawShapeGeometry();
                    return;
                }
                const double scale = 10;
                r = radius / scale;
                CreateAndDrawShapeGeometry();
                toolWidgetManager.drawDoubleAtCursor(onSketchPos, radius);
            } break;
            case SelectMode::SeekFourth: {
                r = std::min(radius, fabs(radius - (onSketchPos - centerPoint).Length()));
                toolWidgetManager.drawDoubleAtCursor(onSketchPos, r);
                CreateAndDrawShapeGeometry();
            } break;
            default:
                break;
        }
    }

    /// The arc from startPoint through `through` to endPoint: its center, radius and angles. False if
    /// the three points are in a line.
    bool arcThroughThreePoints(const Base::Vector2d& through)
    {
        const Base::Vector2d& a = startPoint;
        const Base::Vector2d& b = through;
        const Base::Vector2d& c = endPoint;
        const double d = 2 * (a.x * (b.y - c.y) + b.x * (c.y - a.y) + c.x * (a.y - b.y));
        const double size = std::max((b - a).Length(), (c - a).Length());
        if (fabs(d) < Precision::Confusion() * std::max(size, 1.0)) {
            return false;
        }
        const double a2 = a.Sqr();
        const double b2 = b.Sqr();
        const double c2 = c.Sqr();
        centerPoint.x = (a2 * (b.y - c.y) + b2 * (c.y - a.y) + c2 * (a.y - b.y)) / d;
        centerPoint.y = (a2 * (c.x - b.x) + b2 * (a.x - c.x) + c2 * (b.x - a.x)) / d;
        radius = (a - centerPoint).Length();
        if (radius < Precision::Confusion()) {
            return false;
        }
        const double twoPi = 2 * std::numbers::pi;
        auto turn = [twoPi](double from, double to) {  // counterclockwise, in [0, 2 pi)
            double angle = fmod(to - from, twoPi);
            return angle < 0 ? angle + twoPi : angle;
        };
        const double start = (a - centerPoint).Angle();
        const double toEnd = turn(start, (c - centerPoint).Angle());
        const double toThrough = turn(start, (b - centerPoint).Angle());
        arcAngle = toThrough < toEnd ? toEnd : toEnd - twoPi;
        startAngle = start;
        startAngleBackup = start;
        reverseIfNecessary();
        return true;
    }

    /// The point the arc passes through halfway between the ends, for an arc of radius `arcRadius`
    /// bending toward `pointer` (the shorter of the two such arcs).
    Base::Vector2d arcMiddleForRadius(double arcRadius, const Base::Vector2d& pointer) const
    {
        const Base::Vector2d chord = endPoint - startPoint;
        const double half = chord.Length() / 2;
        const Base::Vector2d middle = startPoint + chord * 0.5;
        Base::Vector2d normal = chord.Perpendicular();
        if (normal.Length() < Precision::Confusion()) {
            return pointer;
        }
        normal.Normalize();
        if ((pointer - middle) * normal < 0) {
            normal = normal * -1.0;  // bend toward the pointer
        }
        arcRadius = std::max(arcRadius, half);
        const double sagitta = arcRadius - std::sqrt(arcRadius * arcRadius - half * half);
        return middle + normal * sagitta;
    }

    bool arcEnds() const
    {
        return constructionMethod() != ConstructionMethod::RectangleSlot;
    }

    void executeCommands() override
    {
        try {
            createShape(false);

            openCommand(QT_TRANSLATE_NOOP("Command", "Add sketch arc slot"));

            commandAddShapeGeometryAndConstraints();

            commitCommand();
        }
        catch (const Base::Exception&) {
            Gui::NotifyError(
                sketchgui,
                QT_TRANSLATE_NOOP("Notifications", "Error"),
                QT_TRANSLATE_NOOP("Notifications", "Failed to add arc slot")
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
        auto& ac2 = sugConstraints[1];
        auto& ac3 = sugConstraints[2];

        if (constructionMethod() == ConstructionMethod::ThreePoint) {
            // the clicks were the ends' centers; the third, on the arc, is no point of the slot's
            generateAutoConstraintsOnElement(sugConstraints[0], getHighestCurveIndex() - 2, Sketcher::PointPos::mid);
            generateAutoConstraintsOnElement(ac2, getHighestCurveIndex() - 1, Sketcher::PointPos::mid);
            ac3.clear();
            removeRedundantAutoConstraints();
            return;
        }

        generateAutoConstraintsOnElement(
            sugConstraints[0],
            getHighestCurveIndex() - 3,
            Sketcher::PointPos::mid
        );  // add auto constraints for the center point

        if (constructionMethod() == ConstructionMethod::ArcSlot) {
            generateAutoConstraintsOnElement(ac2, getHighestCurveIndex() - 2, Sketcher::PointPos::mid);
            generateAutoConstraintsOnElement(ac3, getHighestCurveIndex() - 1, Sketcher::PointPos::mid);
        }
        else {
            generateAutoConstraintsOnElement(
                ac2,
                getHighestCurveIndex() - 3,
                (arcAngle > 0) ? Sketcher::PointPos::start : Sketcher::PointPos::end
            );
            generateAutoConstraintsOnElement(
                ac3,
                getHighestCurveIndex() - 3,
                (arcAngle > 0) ? Sketcher::PointPos::end : Sketcher::PointPos::start
            );
        }

        // Ensure temporary autoconstraints do not generate a redundancy and that the geometry
        // parameters are accurate This is particularly important for adding widget mandated
        // constraints.
        removeRedundantAutoConstraints();
    }

    void createAutoConstraints() override
    {
        // execute python command to create autoconstraints
        createGeneratedAutoConstraints(true);

        sugConstraints[0].clear();
        sugConstraints[1].clear();
        sugConstraints[2].clear();
    }

    std::string getToolName() const override
    {
        return "DSH_ArcSlot";
    }

    QString getCrosshairCursorSVGName() const override
    {
        if (arcEnds()) {
            return QStringLiteral("Sketcher_Pointer_Create_ArcSlot");
        }
        else {
            return QStringLiteral("Sketcher_Pointer_Create_RectangleSlot");
        }
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
        return Gui::BitmapFactory().pixmap("Sketcher_CreateArcSlot");
    }

    QString getToolWidgetText() const override
    {
        return QString(tr("Arc Slot Parameters"));
    }

    bool canGoToNextMode() override
    {
        if (constructionMethod() == ConstructionMethod::ThreePoint) {
            if (state() == SelectMode::SeekSecond
                && (endPoint - startPoint).Length() < Precision::Confusion()) {
                return false;  // the ends in one place
            }
            if (state() == SelectMode::SeekThird
                && (radius < Precision::Confusion() || fabs(arcAngle) < Precision::Confusion())) {
                return false;  // in a line with the ends
            }
        }
        // Prevent validation of null arc.
        else if (state() == SelectMode::SeekSecond && radius < Precision::Confusion()) {
            return false;
        }
        if (state() == SelectMode::SeekThird && fabs(arcAngle) < Precision::Confusion()) {
            return false;
        }
        if (state() == SelectMode::SeekFourth) {
            if (arcEnds()) {
                if (r < Precision::Confusion()) {
                    return false;
                }
            }
            else {
                if (fabs(radius - r) < Precision::Confusion()) {
                    return false;
                }
            }
        }
        return true;
    }

    void angleSnappingControl() override
    {
        if (constructionMethod() == ConstructionMethod::ThreePoint) {
            if (state() == SelectMode::SeekSecond) {
                setAngleSnapping(true, startPoint);
            }
            else {
                setAngleSnapping(false);
            }
            return;
        }
        if (state() == SelectMode::SeekSecond || state() == SelectMode::SeekThird) {
            setAngleSnapping(true, centerPoint);
        }
        else {
            setAngleSnapping(false);
        }
    }

    void createShape(bool onlyeditoutline) override
    {
        using std::numbers::pi;

        ShapeGeometry.clear();

        if (constructionMethod() == ConstructionMethod::ThreePoint && state() == SelectMode::SeekSecond) {
            if ((endPoint - startPoint).Length() > Precision::Confusion()) {  // from end to end, so far
                addLineToShapeGeometry(toVector3d(startPoint), toVector3d(endPoint), isConstructionMode());
            }
            return;
        }

        if (radius < Precision::Confusion()) {
            return;
        }

        if (state() == SelectMode::SeekSecond) {
            addCircleToShapeGeometry(toVector3d(centerPoint), radius, isConstructionMode());
        }
        else {
            if (fabs(arcAngle) < Precision::Confusion()) {
                return;
            }

            if (state() == SelectMode::SeekFourth && r < Precision::Confusion()) {
                return;
            }

            if (arcEnds()) {
                addArcToShapeGeometry(
                    toVector3d(centerPoint),
                    startAngle,
                    endAngle,
                    radius + r,
                    isConstructionMode()
                );

                addArcToShapeGeometry(
                    toVector3d(startPoint),
                    angleReversed ? endAngle : startAngle + pi,
                    angleReversed ? endAngle + pi : startAngle + 2 * pi,
                    r,
                    isConstructionMode()
                );

                addArcToShapeGeometry(
                    toVector3d(endPoint),
                    angleReversed ? startAngle + pi : endAngle,
                    angleReversed ? startAngle + 2 * pi : pi + endAngle,
                    r,
                    isConstructionMode()
                );

                if (radius - r > Precision::Confusion()) {
                    addArcToShapeGeometry(
                        toVector3d(centerPoint),
                        startAngle,
                        endAngle,
                        radius - r,
                        isConstructionMode()
                    );
                }
            }
            else {
                Part::GeomArcOfCircle* arc1 = addArcToShapeGeometry(
                    toVector3d(centerPoint),
                    startAngle,
                    endAngle,
                    radius,
                    isConstructionMode()
                );

                Base::Vector3d p11 = arc1->getStartPoint();
                Base::Vector3d p12 = arc1->getEndPoint();

                if (r > Precision::Confusion()) {
                    auto arc2 = std::make_unique<Part::GeomArcOfCircle>();
                    arc2->setRadius(r);
                    arc2->setRange(startAngle, endAngle, true);
                    arc2->setCenter(toVector3d(centerPoint));
                    Sketcher::GeometryFacade::setConstruction(arc2.get(), isConstructionMode());

                    Base::Vector3d p21 = arc2->getStartPoint();
                    Base::Vector3d p22 = arc2->getEndPoint();

                    addLineToShapeGeometry(p11, p21, isConstructionMode());

                    addLineToShapeGeometry(p12, p22, isConstructionMode());

                    // arc2 is added last to make it easy if it does not exist
                    ShapeGeometry.push_back(std::move(arc2));
                }
                else {
                    addLineToShapeGeometry(p11, toVector3d(centerPoint), isConstructionMode());

                    addLineToShapeGeometry(p12, toVector3d(centerPoint), isConstructionMode());
                }
            }
        }

        if (!onlyeditoutline) {
            int firstCurve = getHighestCurveIndex() + 1;

            if (arcEnds()) {
                bool allArcs = fabs(radius - r) > Precision::Confusion();

                Sketcher::PointPos pos1 = angleReversed ? Sketcher::PointPos::start
                                                        : Sketcher::PointPos::end;
                Sketcher::PointPos pos2 = angleReversed ? Sketcher::PointPos::end
                                                        : Sketcher::PointPos::start;

                if (allArcs) {
                    addToShapeConstraints(
                        Sketcher::Coincident,
                        firstCurve,
                        Sketcher::PointPos::mid,
                        firstCurve + 3,
                        Sketcher::PointPos::mid
                    );

                    addToShapeConstraints(Sketcher::Tangent, firstCurve + 3, pos1, firstCurve + 2, pos1);

                    addToShapeConstraints(Sketcher::Tangent, firstCurve + 3, pos2, firstCurve + 1, pos2);
                }
                else {
                    addToShapeConstraints(
                        Sketcher::Coincident,
                        firstCurve,
                        Sketcher::PointPos::mid,
                        firstCurve + 1,
                        pos2
                    );

                    addToShapeConstraints(
                        Sketcher::Coincident,
                        firstCurve,
                        Sketcher::PointPos::mid,
                        firstCurve + 2,
                        pos1
                    );
                }

                addToShapeConstraints(Sketcher::Tangent, firstCurve, pos1, firstCurve + 2, pos2);

                addToShapeConstraints(Sketcher::Tangent, firstCurve, pos2, firstCurve + 1, pos1);
            }
            else {
                bool allGeos = r > Precision::Confusion();

                addToShapeConstraints(
                    Sketcher::Perpendicular,
                    firstCurve,
                    Sketcher::PointPos::none,
                    firstCurve + 1,
                    Sketcher::PointPos::none
                );

                addToShapeConstraints(
                    Sketcher::Perpendicular,
                    firstCurve,
                    Sketcher::PointPos::none,
                    firstCurve + 2,
                    Sketcher::PointPos::none
                );


                addToShapeConstraints(
                    Sketcher::Coincident,
                    firstCurve,
                    Sketcher::PointPos::start,
                    firstCurve + 1,
                    Sketcher::PointPos::start
                );

                addToShapeConstraints(
                    Sketcher::Coincident,
                    firstCurve,
                    Sketcher::PointPos::end,
                    firstCurve + 2,
                    Sketcher::PointPos::start
                );

                if (allGeos) {
                    addToShapeConstraints(
                        Sketcher::Coincident,
                        firstCurve,
                        Sketcher::PointPos::mid,
                        firstCurve + 3,
                        Sketcher::PointPos::mid
                    );

                    addToShapeConstraints(
                        Sketcher::Coincident,
                        firstCurve + 3,
                        Sketcher::PointPos::start,
                        firstCurve + 1,
                        Sketcher::PointPos::end
                    );

                    addToShapeConstraints(
                        Sketcher::Coincident,
                        firstCurve + 3,
                        Sketcher::PointPos::end,
                        firstCurve + 2,
                        Sketcher::PointPos::end
                    );
                }
                else {
                    addToShapeConstraints(
                        Sketcher::Coincident,
                        firstCurve,
                        Sketcher::PointPos::mid,
                        firstCurve + 1,
                        Sketcher::PointPos::end
                    );

                    addToShapeConstraints(
                        Sketcher::Coincident,
                        firstCurve,
                        Sketcher::PointPos::mid,
                        firstCurve + 2,
                        Sketcher::PointPos::end
                    );
                }
            }
        }
    }

    void reverseIfNecessary()
    {
        if (arcAngle > 0) {
            endAngle = startAngle + arcAngle;
            angleReversed = false;
        }
        else {
            endAngle = startAngle;
            startAngle = startAngle + arcAngle;
            angleReversed = true;
        }
    }

private:
    Base::Vector2d centerPoint, startPoint, endPoint;
    double startAngle, startAngleBackup, endAngle, arcAngle, r, radius;
    bool angleReversed;
};

template<>
auto DSHArcSlotControllerBase::getState(int labelindex) const
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
        case OnViewParameter::Fifth:
            return SelectMode::SeekThird;
            break;
        case OnViewParameter::Sixth:
            return SelectMode::SeekFourth;
            break;
        default:
            THROWM(Base::ValueError, "OnViewParameter index without an associated machine state")
    }
}

template<>
void DSHArcSlotController::configureToolWidget()
{
    if (!init) {  // Code to be executed only upon initialisation
        QStringList names = {
            QApplication::translate("Sketcher_CreateArcSlot", "Arc ends"),
            QApplication::translate("Sketcher_CreateArcSlot", "Flat ends"),
            QApplication::translate("Sketcher_CreateArcSlot", "Three points")
        };
        toolWidget->setComboboxElements(WCombobox::FirstCombo, names);

        if (handler->isConstructionMode()) {
            toolWidget->setComboboxItemIcon(
                WCombobox::FirstCombo,
                0,
                Gui::BitmapFactory().iconFromTheme("Sketcher_CreateArcSlot_Constr")
            );
            toolWidget->setComboboxItemIcon(
                WCombobox::FirstCombo,
                1,
                Gui::BitmapFactory().iconFromTheme("Sketcher_CreateRectangleSlot_Constr")
            );
            toolWidget->setComboboxItemIcon(
                WCombobox::FirstCombo,
                2,
                Gui::BitmapFactory().iconFromTheme("Sketcher_CreateArcSlot_Constr")
            );
        }
        else {
            toolWidget->setComboboxItemIcon(
                WCombobox::FirstCombo,
                0,
                Gui::BitmapFactory().iconFromTheme("Sketcher_CreateArcSlot")
            );
            toolWidget->setComboboxItemIcon(
                WCombobox::FirstCombo,
                1,
                Gui::BitmapFactory().iconFromTheme("Sketcher_CreateRectangleSlot")
            );
            toolWidget->setComboboxItemIcon(
                WCombobox::FirstCombo,
                2,
                Gui::BitmapFactory().iconFromTheme("Sketcher_CreateArcSlot")
            );
        }
    }

    onViewParameters[OnViewParameter::First]->setLabelType(Gui::SoDatumLabel::DISTANCEX);
    onViewParameters[OnViewParameter::Second]->setLabelType(Gui::SoDatumLabel::DISTANCEY);
    if (handler->constructionMethod() == DrawSketchHandlerArcSlot::ConstructionMethod::ThreePoint) {
        // the far end's position, then the radius of the arc through the third point, then the width
        onViewParameters[OnViewParameter::Third]->setLabelType(Gui::SoDatumLabel::DISTANCEX);
        onViewParameters[OnViewParameter::Fourth]->setLabelType(Gui::SoDatumLabel::DISTANCEY);
        onViewParameters[OnViewParameter::Fifth]->setLabelType(
            Gui::SoDatumLabel::RADIUS,
            Gui::EditableDatumLabel::Function::Dimensioning
        );
        onViewParameters[OnViewParameter::Sixth]->setLabelType(
            Gui::SoDatumLabel::RADIUS,
            Gui::EditableDatumLabel::Function::Dimensioning
        );
        return;
    }
    onViewParameters[OnViewParameter::Third]->setLabelType(
        Gui::SoDatumLabel::RADIUS,
        Gui::EditableDatumLabel::Function::Dimensioning
    );
    onViewParameters[OnViewParameter::Fourth]->setLabelType(
        Gui::SoDatumLabel::ANGLE,
        Gui::EditableDatumLabel::Function::Dimensioning
    );
    onViewParameters[OnViewParameter::Fifth]->setLabelType(
        Gui::SoDatumLabel::ANGLE,
        Gui::EditableDatumLabel::Function::Dimensioning
    );

    if (handler->arcEnds()) {
        onViewParameters[OnViewParameter::Sixth]->setLabelType(
            Gui::SoDatumLabel::RADIUS,
            Gui::EditableDatumLabel::Function::Dimensioning
        );
    }
    else {
        onViewParameters[OnViewParameter::Sixth]->setLabelType(
            Gui::SoDatumLabel::DISTANCE,
            Gui::EditableDatumLabel::Function::Dimensioning
        );
    }
}

template<>
void DSHArcSlotControllerBase::doEnforceControlParameters(Base::Vector2d& onSketchPos)
{
    if (handler->constructionMethod() == DrawSketchHandlerArcSlot::ConstructionMethod::ThreePoint) {
        switch (handler->state()) {
            case SelectMode::SeekSecond: {  // the far end, as the first
                auto& thirdParam = onViewParameters[OnViewParameter::Third];
                auto& fourthParam = onViewParameters[OnViewParameter::Fourth];
                if (thirdParam->isSet) {
                    onSketchPos.x = thirdParam->getValue();
                }
                if (fourthParam->isSet) {
                    onSketchPos.y = fourthParam->getValue();
                }
                return;
            }
            case SelectMode::SeekThird: {  // a typed radius: the arc of that radius bending to the pointer
                auto& fifthParam = onViewParameters[OnViewParameter::Fifth];
                if (fifthParam->isSet) {
                    const double arcRadius = fifthParam->getValue();
                    const double half = (handler->endPoint - handler->startPoint).Length() / 2;
                    if (arcRadius < half + Precision::Confusion() && fifthParam->hasFinishedEditing) {
                        unsetOnViewParameter(fifthParam.get());  // too small to reach both ends
                        return;
                    }
                    onSketchPos = handler->arcMiddleForRadius(arcRadius, onSketchPos);
                }
                return;
            }
            default:
                break;  // the first end and the width as Arc ends takes them
        }
    }

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

            auto dir = onSketchPos - handler->centerPoint;
            if (dir.Length() < Precision::Confusion()) {
                dir.x = 1.0;  // if direction null, default to (1,0)
            }
            double radius = dir.Length();

            if (thirdParam->isSet) {
                radius = thirdParam->getValue();
                if (radius < Precision::Confusion() && thirdParam->hasFinishedEditing) {
                    unsetOnViewParameter(thirdParam.get());
                    return;
                }

                onSketchPos = handler->centerPoint + radius * dir.Normalize();
            }

            if (fourthParam->isSet) {
                double angle = Base::toRadians(fourthParam->getValue());
                onSketchPos.x = handler->centerPoint.x + cos(angle) * radius;
                onSketchPos.y = handler->centerPoint.y + sin(angle) * radius;
            }
        } break;
        case SelectMode::SeekThird: {
            auto& fifthParam = onViewParameters[OnViewParameter::Fifth];

            if (fifthParam->isSet) {
                double arcAngle = Base::toRadians(fifthParam->getValue());
                if (fmod(fabs(arcAngle), 2 * std::numbers::pi) < Precision::Confusion()
                    && fifthParam->hasFinishedEditing) {
                    unsetOnViewParameter(fifthParam.get());
                }
                else {
                    handler->arcAngle = arcAngle;

                    double length = (onSketchPos - handler->centerPoint).Length();
                    double angle = handler->startAngleBackup + arcAngle;
                    onSketchPos.x = handler->centerPoint.x + cos(angle) * length;
                    onSketchPos.y = handler->centerPoint.y + sin(angle) * length;
                }
            }
        } break;
        case SelectMode::SeekFourth: {
            auto& sixthParam = onViewParameters[OnViewParameter::Sixth];

            if (sixthParam->isSet) {
                double radius2 = sixthParam->getValue();
                if (((fabs(radius2) < Precision::Confusion() && handler->arcEnds())
                     || (fabs(handler->radius - radius2) < Precision::Confusion()
                         && handler->constructionMethod()
                             == DrawSketchHandlerArcSlot::ConstructionMethod::RectangleSlot))
                    && sixthParam->hasFinishedEditing) {
                    unsetOnViewParameter(sixthParam.get());
                }
                else {
                    onSketchPos = handler->centerPoint
                        + Base::Vector2d(handler->radius + radius2, 0.);
                }
            }
        } break;
        default:
            break;
    }
}

template<>
void DSHArcSlotController::adaptParameters(Base::Vector2d onSketchPos)
{
    if (handler->constructionMethod() == DrawSketchHandlerArcSlot::ConstructionMethod::ThreePoint) {
        switch (handler->state()) {
            case SelectMode::SeekSecond: {
                auto& thirdParam = onViewParameters[OnViewParameter::Third];
                auto& fourthParam = onViewParameters[OnViewParameter::Fourth];
                if (!thirdParam->isSet) {
                    setOnViewParameterValue(OnViewParameter::Third, onSketchPos.x);
                }
                if (!fourthParam->isSet) {
                    setOnViewParameterValue(OnViewParameter::Fourth, onSketchPos.y);
                }
                bool sameSign = onSketchPos.x * onSketchPos.y > 0.;
                thirdParam->setLabelAutoDistanceReverse(!sameSign);
                fourthParam->setLabelAutoDistanceReverse(sameSign);
                thirdParam->setPoints(Base::Vector3d(), toVector3d(onSketchPos));
                fourthParam->setPoints(Base::Vector3d(), toVector3d(onSketchPos));
                return;
            }
            case SelectMode::SeekThird: {
                auto& fifthParam = onViewParameters[OnViewParameter::Fifth];
                if (!fifthParam->isSet) {
                    setOnViewParameterValue(OnViewParameter::Fifth, handler->radius);
                }
                Base::Vector3d center = toVector3d(handler->centerPoint);
                fifthParam->setPoints(center, toVector3d(handler->startPoint));
                return;
            }
            default:
                break;  // the first end and the width as Arc ends shows them
        }
    }

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

            if (!thirdParam->isSet) {
                setOnViewParameterValue(OnViewParameter::Third, handler->radius);
            }
            double range = Base::toDegrees(handler->startAngle);
            if (!fourthParam->isSet) {
                setOnViewParameterValue(OnViewParameter::Fourth, range, Base::Unit::Angle);
            }

            Base::Vector3d start = toVector3d(handler->centerPoint);
            Base::Vector3d end = toVector3d(onSketchPos);

            thirdParam->setPoints(start, end);
            fourthParam->setPoints(start, Base::Vector3d());
            fourthParam->setLabelRange(handler->startAngle);
        } break;
        case SelectMode::SeekThird: {
            auto& fifthParam = onViewParameters[OnViewParameter::Fifth];

            double range = Base::toDegrees(handler->arcAngle);

            if (!fifthParam->isSet) {
                setOnViewParameterValue(OnViewParameter::Fifth, range, Base::Unit::Angle);
            }

            Base::Vector3d start = toVector3d(handler->centerPoint);
            fifthParam->setPoints(start, Base::Vector3d());

            fifthParam->setLabelStartAngle(handler->startAngleBackup);
            fifthParam->setLabelRange(handler->arcAngle);
        } break;
        case SelectMode::SeekFourth: {
            auto& sixthParam = onViewParameters[OnViewParameter::Sixth];

            double dist = handler->r;
            if (handler->constructionMethod()
                == DrawSketchHandlerArcSlot::ConstructionMethod::RectangleSlot) {
                dist = (handler->r - handler->radius);
            }

            if (!sixthParam->isSet) {
                setOnViewParameterValue(OnViewParameter::Sixth, dist);
            }

            Base::Vector3d start = toVector3d(handler->endPoint);
            Base::Vector3d end = start
                + (start - toVector3d(handler->centerPoint)).Normalize() * dist;

            sixthParam->setPoints(start, end);
        } break;
        default:
            break;
    }
}

template<>
void DSHArcSlotController::computeNextDrawSketchHandlerMode()
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
                handler->setNextState(SelectMode::SeekThird);
            }
        } break;
        case SelectMode::SeekThird: {
            auto& fifthParam = onViewParameters[OnViewParameter::Fifth];

            if (fifthParam->hasFinishedEditing) {
                handler->setNextState(SelectMode::SeekFourth);
            }
        } break;
        case SelectMode::SeekFourth: {
            auto& sixthParam = onViewParameters[OnViewParameter::Sixth];

            if (sixthParam->hasFinishedEditing) {
                handler->setNextState(SelectMode::End);
            }
        } break;
        default:
            break;
    }
}

template<>
void DSHArcSlotController::addConstraints()
{
    App::DocumentObject* obj = handler->sketchgui->getObject();

    int firstCurve = handler->getHighestCurveIndex() - 3;
    using namespace Sketcher;

    if (handler->constructionMethod() == DrawSketchHandlerArcSlot::ConstructionMethod::ThreePoint) {
        // Typed: the ends' centers (First, Second; Third, Fourth), the arc's radius (Fifth: from the
        // slot's center to an end's center), the ends' radius (Sixth). A position only where an
        // automatic constraint left the point free to move that way.
        const bool checkFreedom = !handler->AutoConstraints.empty();
        auto place = [&](int geoId, auto& xParam, auto& yParam) {
            if (xParam->isSet
                && (!checkFreedom || handler->getPointInfo(GeoElementId(geoId, PointPos::mid)).isXDoF())) {
                ConstraintToAttachment(GeoElementId(geoId, PointPos::mid), GeoElementId::VAxis, xParam->getValue(), obj);
                if (checkFreedom) {
                    handler->diagnoseWithAutoConstraints();
                }
            }
            if (yParam->isSet
                && (!checkFreedom || handler->getPointInfo(GeoElementId(geoId, PointPos::mid)).isYDoF())) {
                ConstraintToAttachment(GeoElementId(geoId, PointPos::mid), GeoElementId::HAxis, yParam->getValue(), obj);
                if (checkFreedom) {
                    handler->diagnoseWithAutoConstraints();
                }
            }
        };
        place(firstCurve + 1, onViewParameters[OnViewParameter::First], onViewParameters[OnViewParameter::Second]);
        place(firstCurve + 2, onViewParameters[OnViewParameter::Third], onViewParameters[OnViewParameter::Fourth]);
        if (onViewParameters[OnViewParameter::Fifth]->isSet) {
            Gui::cmdAppObjectArgs(
                obj,
                "addConstraint(Sketcher.Constraint('Distance',%d,%d,%d,%d,%f)) ",
                firstCurve,
                3,
                firstCurve + 2,
                3,
                fabs(onViewParameters[OnViewParameter::Fifth]->getValue())
            );
        }
        if (onViewParameters[OnViewParameter::Sixth]->isSet) {
            Gui::cmdAppObjectArgs(
                obj,
                "addConstraint(Sketcher.Constraint('Radius',%d,%f)) ",
                firstCurve + 2,
                fabs(onViewParameters[OnViewParameter::Sixth]->getValue())
            );
        }
        return;
    }

    auto x0 = onViewParameters[OnViewParameter::First]->getValue();
    auto y0 = onViewParameters[OnViewParameter::Second]->getValue();
    auto radius = onViewParameters[OnViewParameter::Third]->getValue();
    auto slotRadius = onViewParameters[OnViewParameter::Sixth]->getValue();

    auto x0set = onViewParameters[OnViewParameter::First]->isSet;
    auto y0set = onViewParameters[OnViewParameter::Second]->isSet;
    auto radiusSet = onViewParameters[OnViewParameter::Third]->isSet;
    auto arcAngleSet = onViewParameters[OnViewParameter::Fifth]->isSet;
    auto slotRadiusSet = onViewParameters[OnViewParameter::Sixth]->isSet;

    auto constraintx0 = [&]() {
        ConstraintToAttachment(GeoElementId(firstCurve, PointPos::mid), GeoElementId::VAxis, x0, obj);
    };

    auto constrainty0 = [&]() {
        ConstraintToAttachment(GeoElementId(firstCurve, PointPos::mid), GeoElementId::HAxis, y0, obj);
    };

    auto constraintRadius = [&]() {
        if (handler->arcEnds()) {
            Gui::cmdAppObjectArgs(
                obj,
                "addConstraint(Sketcher.Constraint('Distance',%d,%d,%d,%d,%f)) ",
                firstCurve,
                3,
                firstCurve + 2,
                3,
                fabs(radius)
            );
        }
        else {
            Gui::cmdAppObjectArgs(
                obj,
                "addConstraint(Sketcher.Constraint('Radius',%d,%f)) ",
                firstCurve,
                fabs(radius)
            );
        }
    };

    auto constraintArcAngle = [&]() {
        Gui::cmdAppObjectArgs(
            obj,
            "addConstraint(Sketcher.Constraint('Angle',%d,%f)) ",
            firstCurve,
            fabs(handler->arcAngle)
        );
    };

    auto constraintSlotRadius = [&]() {
        if (handler->arcEnds()) {
            Gui::cmdAppObjectArgs(
                obj,
                "addConstraint(Sketcher.Constraint('Radius',%d,%f)) ",
                firstCurve + 2,
                fabs(slotRadius)
            );
        }
        else {
            Gui::cmdAppObjectArgs(
                obj,
                "addConstraint(Sketcher.Constraint('Distance',%d,%f)) ",
                firstCurve + 2,
                fabs(slotRadius)
            );
        }
    };

    if (handler->AutoConstraints.empty()) {  // No valid diagnosis. Every constraint can be added.
        if (x0set && y0set && x0 == 0. && y0 == 0.) {
            ConstraintToAttachment(GeoElementId(firstCurve, PointPos::mid), GeoElementId::RtPnt, 0., obj);
        }
        else {
            if (x0set) {
                constraintx0();
            }

            if (y0set) {
                constrainty0();
            }
        }

        if (radiusSet) {
            constraintRadius();
        }

        if (arcAngleSet) {
            constraintArcAngle();
        }

        if (slotRadiusSet) {
            constraintSlotRadius();
        }
    }
    else {  // Valid diagnosis. Must check which constraints may be added.
        auto startpointinfo = handler->getPointInfo(GeoElementId(firstCurve, PointPos::mid));

        if (x0set && startpointinfo.isXDoF()) {
            constraintx0();

            handler->diagnoseWithAutoConstraints();  // ensure we have recalculated parameters after
                                                     // each constraint addition
            // get updated point position
            startpointinfo = handler->getPointInfo(GeoElementId(firstCurve, PointPos::mid));
        }

        if (y0set && startpointinfo.isYDoF()) {
            constrainty0();

            handler->diagnoseWithAutoConstraints();  // ensure we have recalculated parameters after
                                                     // each constraint addition
            // get updated point position
            startpointinfo = handler->getPointInfo(GeoElementId(firstCurve, PointPos::mid));
        }


        startpointinfo = handler->getPointInfo(GeoElementId(firstCurve, PointPos::start));
        auto endpointinfo = handler->getPointInfo(GeoElementId(firstCurve, PointPos::end));
        auto midpointinfo = handler->getPointInfo(GeoElementId(firstCurve, PointPos::mid));

        int DoFs = startpointinfo.getDoFs();
        DoFs += endpointinfo.getDoFs();
        DoFs += midpointinfo.getDoFs();

        if (radiusSet && DoFs > 0) {
            constraintRadius();
            DoFs--;
        }

        if (arcAngleSet && DoFs > 0) {
            constraintArcAngle();
        }

        startpointinfo = handler->getPointInfo(GeoElementId(firstCurve + 2, PointPos::start));
        endpointinfo = handler->getPointInfo(GeoElementId(firstCurve + 2, PointPos::end));

        DoFs = startpointinfo.getDoFs();
        DoFs += endpointinfo.getDoFs();

        if (handler->arcEnds()) {
            midpointinfo = handler->getPointInfo(GeoElementId(firstCurve + 2, PointPos::mid));
            DoFs += midpointinfo.getDoFs();
        }

        if (slotRadiusSet && DoFs > 0) {
            constraintSlotRadius();
        }
    }
}

}  // namespace SketcherGui
