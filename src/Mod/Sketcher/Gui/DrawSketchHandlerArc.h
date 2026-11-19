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

#include <Base/Tools.h>
#include <Gui/BitmapFactory.h>
#include <Gui/Notifications.h>
#include <Gui/CommandT.h>
#include <Gui/MainWindow.h>
#include <Gui/InputHint.h>
#include <Mod/Part/App/Geometry2d.h>

#include <Mod/Sketcher/App/SketchObject.h>

#include "DrawSketchDefaultWidgetController.h"
#include "DrawSketchControllableHandler.h"
#include "Utils.h"
#include "ViewProviderSketch.h"

#include "CircleEllipseConstructionMethod.h"

#include <vector>
#include <algorithm>

using namespace std;

namespace SketcherGui
{

class DrawSketchHandlerArc;

namespace ConstructionMethods
{

// The arc's own methods: the first two as CircleEllipseConstructionMethod's, which the circle and the
// ellipse share; a method added here doesn't appear in their tools.
enum class ArcConstructionMethod
{
    Center,
    ThreeRim,
    Tangent,  // from the end of a line or arc, carrying on its direction
    End       // Must be the last one
};

}  // namespace ConstructionMethods

using DSHArcController = DrawSketchDefaultWidgetController<
    DrawSketchHandlerArc,
    StateMachines::ThreeSeekEnd,
    /*PAutoConstraintSize =*/3,
    // Tangent uses four (the fifth is configured with the others, never shown)
    /*OnViewParametersT =*/OnViewParameters<5, 6, 5>,  // NOLINT
    /*WidgetParametersT =*/WidgetParameters<0, 0, 0>,  // NOLINT
    /*WidgetCheckboxesT =*/WidgetCheckboxes<0, 0, 0>,  // NOLINT
    /*WidgetComboboxesT =*/WidgetComboboxes<1, 1, 1>,  // NOLINT,
    /*WidgetLineEditsT =*/WidgetLineEdits<0, 0, 0>,
    ConstructionMethods::ArcConstructionMethod,
    /*bool PFirstComboboxIsConstructionMethod =*/true>;

using DSHArcControllerBase = DSHArcController::ControllerBase;

using DrawSketchHandlerArcBase = DrawSketchControllableHandler<DSHArcController>;

class DrawSketchHandlerArc: public DrawSketchHandlerArcBase
{
    Q_DECLARE_TR_FUNCTIONS(SketcherGui::DrawSketchHandlerArc)

    friend DSHArcController;
    friend DSHArcControllerBase;

public:
    explicit DrawSketchHandlerArc(ConstructionMethod constrMethod = ConstructionMethod::Center)
        : DrawSketchHandlerArcBase(constrMethod)
        , radius(0.0)
        , startAngle(0.0)
        , endAngle(0.0)
        , arcAngle(0.0)
        , arcPos1(Sketcher::PointPos::none)
        , arcPos2(Sketcher::PointPos::none)
    {}

    ~DrawSketchHandlerArc() override = default;

private:
    std::list<Gui::InputHint> getToolHints() const override
    {
        using State = std::pair<ConstructionMethod, SelectMode>;
        using enum Gui::InputHint::UserInput;

        const Gui::InputHint switchModeHint {tr("%1 switch mode"), {KeyM}};

        return Gui::lookupHints<State>(
            {constructionMethod(), state()},
            {
                // Center method
                {.state = {ConstructionMethod::Center, SelectMode::SeekFirst},
                 .hints =
                     {
                         {tr("%1 pick arc center"), {MouseLeft}},
                         switchModeHint,
                     }},
                {.state = {ConstructionMethod::Center, SelectMode::SeekSecond},
                 .hints =
                     {
                         {tr("%1 pick arc start point"), {MouseLeft}},
                         switchModeHint,
                     }},
                {.state = {ConstructionMethod::Center, SelectMode::SeekThird},
                 .hints =
                     {
                         {tr("%1 pick arc end point"), {MouseLeft}},
                         switchModeHint,
                     }},

                // ThreeRim method
                {.state = {ConstructionMethod::ThreeRim, SelectMode::SeekFirst},
                 .hints =
                     {
                         {tr("%1 pick first arc point"), {MouseLeft}},
                         switchModeHint,
                     }},
                {.state = {ConstructionMethod::ThreeRim, SelectMode::SeekSecond},
                 .hints =
                     {
                         {tr("%1 pick second arc point"), {MouseLeft}},
                         switchModeHint,
                     }},
                {.state = {ConstructionMethod::ThreeRim, SelectMode::SeekThird},
                 .hints =
                     {
                         {tr("%1 pick third arc point"), {MouseLeft}},
                         switchModeHint,
                     }},

                // Tangent method
                {.state = {ConstructionMethod::Tangent, SelectMode::SeekFirst},
                 .hints =
                     {
                         {tr("%1 pick the end of a line or arc"), {MouseLeft}},
                         switchModeHint,
                     }},
                {.state = {ConstructionMethod::Tangent, SelectMode::SeekSecond},
                 .hints =
                     {
                         {tr("%1 pick arc end point"), {MouseLeft}},
                         switchModeHint,
                     }},
            });
    }

    void updateDataAndDrawToPosition(Base::Vector2d onSketchPos) override
    {
        switch (state()) {
            case SelectMode::SeekFirst: {
                toolWidgetManager.drawPositionAtCursor(onSketchPos);

                if (constructionMethod() == ConstructionMethod::Center) {
                    centerPoint = onSketchPos;
                }
                else {
                    firstPoint = onSketchPos;
                }

                seekAndRenderAutoConstraint(sugConstraints[0], onSketchPos, Base::Vector2d(0.f, 0.f));

                if (isTangent()) {
                    findTangentStart();  // the end of a line or arc under the pointer, if any
                }
            } break;
            case SelectMode::SeekSecond: {
                if (isTangent()) {
                    secondPoint = onSketchPos;
                    placeTangentArc();
                    CreateAndDrawShapeGeometry();
                    toolWidgetManager.drawPositionAtCursor(onSketchPos);
                    seekAndRenderAutoConstraint(sugConstraints[1], onSketchPos, Base::Vector2d(0.f, 0.f));
                    break;
                }

                if (constructionMethod() == ConstructionMethod::Center) {
                    firstPoint = onSketchPos;
                    startAngle = (firstPoint - centerPoint).Angle();
                }
                else {
                    centerPoint = (onSketchPos - firstPoint) / 2 + firstPoint;
                    secondPoint = onSketchPos;
                }

                radius = (onSketchPos - centerPoint).Length();

                CreateAndDrawShapeGeometry();

                if (constructionMethod() == ConstructionMethod::Center) {
                    toolWidgetManager.drawDirectionAtCursor(onSketchPos, centerPoint);
                }
                else {
                    toolWidgetManager.drawPositionAtCursor(onSketchPos);
                }

                seekAndRenderAutoConstraint(sugConstraints[1], onSketchPos, Base::Vector2d(0.f, 0.f));
            } break;
            case SelectMode::SeekThird: {
                double startAngleBackup = startAngle;

                if (constructionMethod() == ConstructionMethod::Center) {
                    secondPoint = onSketchPos;
                    double angle1 = (onSketchPos - centerPoint).Angle() - startAngle;
                    double angle2 = angle1 + (angle1 < 0. ? 2 : -2) * std::numbers::pi;
                    arcAngle = abs(angle1 - arcAngle) < abs(angle2 - arcAngle) ? angle1 : angle2;

                    if (arcAngle > 0) {
                        endAngle = startAngle + arcAngle;
                    }
                    else {
                        endAngle = startAngle;
                        startAngle = startAngle + arcAngle;
                    }
                }
                else {
                    if (areCollinear(firstPoint, secondPoint, onSketchPos)) {
                        // If points are collinear then we can't calculate the center.
                        return;
                    }
                    centerPoint
                        = Part::Geom2dCircle::getCircleCenter(firstPoint, secondPoint, onSketchPos);
                    radius = (onSketchPos - centerPoint).Length();

                    double angle1 = (firstPoint - centerPoint).Angle();
                    double angle2 = (secondPoint - centerPoint).Angle();
                    double angle3 = (onSketchPos - centerPoint).Angle();

                    // Always build arc counter-clockwise
                    // Point 3 is between Point 1 and 2
                    if (angle3 > std::min(angle1, angle2) && angle3 < std::max(angle1, angle2)) {
                        if (angle2 > angle1) {
                            arcPos1 = Sketcher::PointPos::start;
                            arcPos2 = Sketcher::PointPos::end;
                        }
                        else {
                            arcPos1 = Sketcher::PointPos::end;
                            arcPos2 = Sketcher::PointPos::start;
                        }
                        startAngle = std::min(angle1, angle2);
                        endAngle = std::max(angle1, angle2);
                        arcAngle = endAngle - startAngle;
                    }
                    // Point 3 is not between Point 1 and 2
                    else {
                        if (angle2 > angle1) {
                            arcPos1 = Sketcher::PointPos::end;
                            arcPos2 = Sketcher::PointPos::start;
                        }
                        else {
                            arcPos1 = Sketcher::PointPos::start;
                            arcPos2 = Sketcher::PointPos::end;
                        }
                        startAngle = std::max(angle1, angle2);
                        endAngle = std::min(angle1, angle2);
                        arcAngle = 2 * std::numbers::pi - (startAngle - endAngle);
                    }
                }

                CreateAndDrawShapeGeometry();

                if (constructionMethod() == ConstructionMethod::Center) {
                    startAngle = startAngleBackup;
                    toolWidgetManager.drawDoubleAtCursor(onSketchPos, arcAngle, Base::Unit::Angle);
                    seekAndRenderAutoConstraint(sugConstraints[2], onSketchPos, Base::Vector2d(0.0, 0.0));
                }
                else {
                    toolWidgetManager.drawPositionAtCursor(onSketchPos);
                    seekAndRenderAutoConstraint(
                        sugConstraints[2],
                        onSketchPos,
                        Base::Vector2d(0.f, 0.f),
                        AutoConstraint::CURVE
                    );
                }

            } break;
            default:
                break;
        }
    }

    void executeCommands() override
    {
        if (constructionMethod() == ConstructionMethod::Center) {
            if (arcAngle > 0) {
                endAngle = startAngle + arcAngle;
            }
            else {
                endAngle = startAngle;
                startAngle += arcAngle;
            }
        }

        try {
            createShape(false);

            openCommand(QT_TRANSLATE_NOOP("Command", "Add sketch arc"));

            commandAddShapeGeometryAndConstraints();

            commitCommand();
        }
        catch (const Base::Exception&) {
            /*Gui::NotifyError(sketchgui,
                QT_TRANSLATE_NOOP("Notifications", "Error"),
                QT_TRANSLATE_NOOP("Notifications", "Failed to add arc"));*/

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
        int ArcGeoId = getHighestCurveIndex();

        auto& ac1 = sugConstraints[0];
        auto& ac2 = sugConstraints[1];
        auto& ac3 = sugConstraints[2];

        if (isTangent()) {
            // The start is held by the tangency to the line or arc (which makes them meet too);
            // only the end takes the second click's constraints.
            generateAutoConstraintsOnElement(
                ac2,
                ArcGeoId,
                arcPosAtStart == Sketcher::PointPos::start ? Sketcher::PointPos::end
                                                           : Sketcher::PointPos::start
            );
            removeRedundantAutoConstraints();
            return;
        }

        if (constructionMethod() == ConstructionMethod::Center) {
            // Prevent overconstraining when the arc center is placed symmetrically (at the midpoint)
            // of a line and the arc endpoints are coincident with the endpoints of the same line.
            Sketcher::SketchObject* sketchObj = sketchgui->getSketchObject();
            for (auto& centerAC : ac1) {
                if (centerAC.Type == Sketcher::ConstraintType::Symmetric) {
                    int lineGeoId = centerAC.GeoId;

                    auto isCoincidentToLineEndpoint = [sketchObj, lineGeoId](const auto& ac) {
                        if (ac.Type != Sketcher::ConstraintType::Coincident) {
                            return false;
                        }
                        return sketchObj->arePointsCoincident(
                                   ac.GeoId,
                                   ac.PosId,
                                   lineGeoId,
                                   Sketcher::PointPos::start
                               )
                            || sketchObj->arePointsCoincident(
                                ac.GeoId,
                                ac.PosId,
                                lineGeoId,
                                Sketcher::PointPos::end
                            );
                    };

                    bool startCoincident
                        = std::any_of(ac2.begin(), ac2.end(), isCoincidentToLineEndpoint);
                    bool endCoincident
                        = std::any_of(ac3.begin(), ac3.end(), isCoincidentToLineEndpoint);

                    if (startCoincident && endCoincident) {
                        // Change symmetry to PointOnObject to maintain center on line without
                        // overconstraining
                        centerAC.Type = Sketcher::ConstraintType::PointOnObject;
                    }
                }
            }

            generateAutoConstraintsOnElement(
                ac1,
                ArcGeoId,
                Sketcher::PointPos::mid
            );  // add auto constraints for the center point
            generateAutoConstraintsOnElement(
                ac2,
                ArcGeoId,
                (arcAngle > 0) ? Sketcher::PointPos::start : Sketcher::PointPos::end
            );
            generateAutoConstraintsOnElement(
                ac3,
                ArcGeoId,
                (arcAngle > 0) ? Sketcher::PointPos::end : Sketcher::PointPos::start
            );
        }
        else {
            generateAutoConstraintsOnElement(
                ac1,
                ArcGeoId,
                arcPos1
            );  // add auto constraints for the second picked point
            generateAutoConstraintsOnElement(
                ac2,
                ArcGeoId,
                arcPos2
            );  // add auto constraints for thesecond picked point
            generateAutoConstraintsOnElement(
                ac3,
                ArcGeoId,
                Sketcher::PointPos::none
            );  // add auto constraints for the third picked point
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
        return "DSH_Arc";
    }

    QString getCrosshairCursorSVGName() const override
    {
        if (constructionMethod() == DrawSketchHandlerArc::ConstructionMethod::Center) {
            return QStringLiteral("Sketcher_Pointer_Create_Arc");
        }
        else {  // constructionMethod == DrawSketchHandlerArc::ConstructionMethod::ThreeRim
            return QStringLiteral("Sketcher_Pointer_Create_3PointArc");
        }

        return QStringLiteral("None");
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
        return Gui::BitmapFactory().pixmap("Sketcher_CreateArc");
    }

    QString getToolWidgetText() const override
    {
        return QString(tr("Arc Parameters"));
    }

    bool canGoToNextMode() override
    {
        if (isTangent() && state() == SelectMode::SeekFirst) {
            return tangentGeoId != Sketcher::GeoEnum::GeoUndef;  // only from the end of a line or arc
        }
        if (isTangent() && state() == SelectMode::SeekSecond) {
            return radius > Precision::Confusion() && fabs(arcAngle) > Precision::Confusion();
        }
        if (state() == SelectMode::SeekSecond && radius < Precision::Confusion()) {
            // Prevent validation of null arc.
            return false;
        }
        if (state() == SelectMode::SeekThird && fabs(arcAngle) < Precision::Confusion()) {
            return false;
        }
        return true;
    }

    // reimplement because the tangent arc is 2 steps while the others are 3
    void onButtonPressed(Base::Vector2d onSketchPos) override
    {
        this->updateDataAndDrawToPosition(onSketchPos);
        if (canGoToNextMode()) {
            if (isTangent() && state() == SelectMode::SeekSecond) {
                setState(SelectMode::End);
            }
            else {
                moveToNextMode();
            }
        }
    }

    void angleSnappingControl() override
    {
        if (constructionMethod() == ConstructionMethod::Center
            && (state() == SelectMode::SeekSecond || state() == SelectMode::SeekThird)) {
            setAngleSnapping(true, centerPoint);
        }
        else {
            setAngleSnapping(false);
        }
    }

    void createShape(bool onlyeditoutline) override
    {

        ShapeGeometry.clear();

        if (radius < Precision::Confusion()) {
            return;
        }

        if (state() == SelectMode::SeekSecond && !isTangent()) {
            addCircleToShapeGeometry(toVector3d(centerPoint), radius, isConstructionMode());
        }
        else {
            if (fabs(arcAngle) < Precision::Confusion()) {
                return;
            }

            addArcToShapeGeometry(
                toVector3d(centerPoint),
                startAngle,
                endAngle,
                radius,
                isConstructionMode()
            );
        }

        if (isTangent()) {
            if (!onlyeditoutline) {
                // tangent to the line or arc it starts from, end to end (so they meet too)
                addToShapeConstraints(
                    Sketcher::Tangent,
                    getHighestCurveIndex() + 1,
                    arcPosAtStart,
                    tangentGeoId,
                    tangentPos
                );
            }
            return;
        }

        if (onlyeditoutline) {
            if (constructionMethod() == ConstructionMethod::Center) {
                if (state() == SelectMode::SeekThird) {
                    const double scale = 0.8;
                    addLineToShapeGeometry(
                        toVector3d(centerPoint),
                        Base::Vector3d(
                            centerPoint.x + cos(startAngle) * scale * radius,
                            centerPoint.y + sin(startAngle) * scale * radius,
                            0.
                        ),
                        isConstructionMode()
                    );

                    addLineToShapeGeometry(
                        toVector3d(centerPoint),
                        Base::Vector3d(
                            centerPoint.x + cos(endAngle) * scale * radius,
                            centerPoint.y + sin(endAngle) * scale * radius,
                            0.
                        ),
                        isConstructionMode()
                    );
                }
            }
            else {
                if (state() == SelectMode::SeekSecond) {
                    addLineToShapeGeometry(
                        toVector3d(firstPoint),
                        toVector3d(secondPoint),
                        isConstructionMode()
                    );
                }
                else if (state() == SelectMode::SeekThird) {
                    const double scale = 0.8;
                    addLineToShapeGeometry(
                        toVector3d(centerPoint),
                        toVector3d(centerPoint)
                            + (toVector3d(secondPoint) - toVector3d(centerPoint)) * scale,
                        isConstructionMode()
                    );

                    addLineToShapeGeometry(
                        toVector3d(centerPoint),
                        toVector3d(centerPoint)
                            + (toVector3d(firstPoint) - toVector3d(centerPoint)) * scale,
                        isConstructionMode()
                    );
                }
            }
        }
    }

    bool isTangent() const
    {
        return constructionMethod() == ConstructionMethod::Tangent;
    }

    /// Tangent: the line or arc end the first click snapped to (from the autoconstraint suggested
    /// there), and the direction it heads out of that end.
    bool findTangentStart()
    {
        tangentGeoId = Sketcher::GeoEnum::GeoUndef;
        auto* sketch = getSketchObject();
        for (const auto& ac : sugConstraints[0]) {
            if (ac.Type != Sketcher::Coincident
                || (ac.PosId != Sketcher::PointPos::start && ac.PosId != Sketcher::PointPos::end)
                || ac.GeoId == Sketcher::GeoEnum::HAxis || ac.GeoId == Sketcher::GeoEnum::VAxis) {
                continue;
            }
            const Part::Geometry* geo = sketch->getGeometry(ac.GeoId);
            if (!geo || !(geo->is<Part::GeomLineSegment>() || geo->is<Part::GeomArcOfCircle>())) {
                continue;
            }
            auto* curve = static_cast<const Part::GeomCurve*>(geo);
            const bool atStart = ac.PosId == Sketcher::PointPos::start;
            Base::Vector3d dir;
            if (!curve->tangent(atStart ? curve->getFirstParameter() : curve->getLastParameter(), dir)) {
                continue;
            }
            if (atStart) {
                dir = -dir;  // carry on out of the start
            }
            tangentDir = Base::Vector2d(dir.x, dir.y);
            if (tangentDir.Length() < Precision::Confusion()) {
                continue;
            }
            tangentDir.Normalize();
            const Base::Vector3d end = sketch->getPoint(ac.GeoId, ac.PosId);
            firstPoint = Base::Vector2d(end.x, end.y);
            tangentGeoId = ac.GeoId;
            tangentPos = ac.PosId;
            return true;
        }
        return false;
    }

    /// Tangent: the arc from the start, heading along tangentDir, through secondPoint. Its center
    /// is square to the direction, as far from the start as from the end; it turns towards the end.
    void placeTangentArc()
    {
        const Base::Vector2d chord = secondPoint - firstPoint;
        const Base::Vector2d left(-tangentDir.y, tangentDir.x);
        const double across = chord * left;
        if (tangentGeoId == Sketcher::GeoEnum::GeoUndef || fabs(across) < Precision::Confusion()) {
            radius = 0.0;  // straight ahead: no arc
            arcAngle = 0.0;
            return;
        }
        const double offset = (chord * chord) / (2 * across);  // > 0: the center on the left
        centerPoint = firstPoint + offset * left;
        radius = fabs(offset);

        const double fromAngle = (firstPoint - centerPoint).Angle();
        const double toAngle = (secondPoint - centerPoint).Angle();
        // Arcs go counterclockwise: from the start when turning left, from the end when turning right
        startAngle = offset > 0 ? fromAngle : toAngle;
        endAngle = offset > 0 ? toAngle : fromAngle;
        arcPosAtStart = offset > 0 ? Sketcher::PointPos::start : Sketcher::PointPos::end;
        if (endAngle <= startAngle) {
            endAngle += 2 * std::numbers::pi;
        }
        arcAngle = endAngle - startAngle;
    }

private:
    Base::Vector2d centerPoint, firstPoint, secondPoint;
    double radius, startAngle, endAngle, arcAngle;
    Sketcher::PointPos arcPos1, arcPos2;

    // Tangent: the line or arc end it starts from, the way it heads there, and which end of the
    // new arc meets it
    int tangentGeoId = Sketcher::GeoEnum::GeoUndef;
    Sketcher::PointPos tangentPos = Sketcher::PointPos::none;
    Base::Vector2d tangentDir;
    Sketcher::PointPos arcPosAtStart = Sketcher::PointPos::start;
};

template<>
auto DSHArcControllerBase::getState(int labelindex) const
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
        case OnViewParameter::Sixth:
            return SelectMode::SeekThird;
            break;
        default:
            THROWM(Base::ValueError, "OnViewParameter index without an associated machine state")
    }
}

template<>
void DSHArcController::configureToolWidget()
{
    if (!init) {  // Code to be executed only upon initialisation
        QStringList names = {
            QApplication::translate("Sketcher_CreateArc", "Center"),
            QApplication::translate("Sketcher_CreateArc", "3 rim points"),
            QApplication::translate("Sketcher_CreateArc", "Tangent (from the end of a line or arc)")
        };
        toolWidget->setComboboxElements(WCombobox::FirstCombo, names);
        toolWidget->setComboboxItemIcon(
            WCombobox::FirstCombo,
            2,
            Gui::BitmapFactory().iconFromTheme(
                handler->isConstructionMode() ? "Sketcher_CreateArc_Constr" : "Sketcher_CreateArc"
            )
        );

        if (handler->isConstructionMode()) {
            toolWidget->setComboboxItemIcon(
                WCombobox::FirstCombo,
                0,
                Gui::BitmapFactory().iconFromTheme("Sketcher_CreateArc_Constr")
            );
            toolWidget->setComboboxItemIcon(
                WCombobox::FirstCombo,
                1,
                Gui::BitmapFactory().iconFromTheme("Sketcher_Create3PointArc_Constr")
            );
        }
        else {
            toolWidget->setComboboxItemIcon(
                WCombobox::FirstCombo,
                0,
                Gui::BitmapFactory().iconFromTheme("Sketcher_CreateArc")
            );
            toolWidget->setComboboxItemIcon(
                WCombobox::FirstCombo,
                1,
                Gui::BitmapFactory().iconFromTheme("Sketcher_Create3PointArc")
            );
        }
    }

    onViewParameters[OnViewParameter::First]->setLabelType(Gui::SoDatumLabel::DISTANCEX);
    onViewParameters[OnViewParameter::Second]->setLabelType(Gui::SoDatumLabel::DISTANCEY);

    if (handler->constructionMethod() == DrawSketchHandlerArc::ConstructionMethod::ThreeRim) {
        onViewParameters[OnViewParameter::Third]->setLabelType(Gui::SoDatumLabel::DISTANCEX);
        onViewParameters[OnViewParameter::Fourth]->setLabelType(Gui::SoDatumLabel::DISTANCEY);

        onViewParameters[OnViewParameter::Fifth]->setLabelType(Gui::SoDatumLabel::DISTANCEX);
        onViewParameters[OnViewParameter::Sixth]->setLabelType(Gui::SoDatumLabel::DISTANCEY);
    }
    else {
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
    }
}

template<>
void DSHArcControllerBase::doEnforceControlParameters(Base::Vector2d& onSketchPos)
{
    switch (handler->state()) {
        case SelectMode::SeekFirst: {
            auto& firstParam = onViewParameters[OnViewParameter::First];
            auto& secondParam = onViewParameters[OnViewParameter::Second];

            if (handler->isTangent()) {
                break;  // it starts where a line or arc ends: picked, not typed
            }

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

            if (handler->isTangent()) {
                // the radius, and how far round (degrees); the side the pointer is on sets the turn
                if (!thirdParam->isSet && !fourthParam->isSet) {
                    break;
                }
                const Base::Vector2d start = handler->firstPoint;
                const Base::Vector2d left(-handler->tangentDir.y, handler->tangentDir.x);
                const double side = (onSketchPos - start) * left >= 0 ? 1.0 : -1.0;
                double radius = handler->radius;
                if (thirdParam->isSet) {
                    radius = thirdParam->getValue();
                    if (radius < Precision::Confusion() && thirdParam->hasFinishedEditing) {
                        unsetOnViewParameter(thirdParam.get());
                        return;
                    }
                }
                if (radius < Precision::Confusion()) {
                    break;
                }
                const Base::Vector2d center = start + side * radius * left;
                if (fourthParam->isSet) {
                    Base::Vector2d spoke = start - center;
                    spoke.Rotate(side * Base::toRadians(fourthParam->getValue()));
                    onSketchPos = center + spoke;
                }
                else {
                    Base::Vector2d dir = onSketchPos - center;
                    if (dir.Length() < Precision::Confusion()) {
                        dir = start - center;
                    }
                    onSketchPos = center + radius * dir.Normalize();
                }
                break;
            }

            if (handler->constructionMethod() == DrawSketchHandlerArc::ConstructionMethod::Center) {
                Base::Vector2d dir = onSketchPos - handler->centerPoint;
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
            }
            else {
                if (thirdParam->isSet) {
                    onSketchPos.x = thirdParam->getValue();
                }

                if (fourthParam->isSet) {
                    onSketchPos.y = fourthParam->getValue();
                }
                if (thirdParam->hasFinishedEditing && fourthParam->hasFinishedEditing
                    && (onSketchPos - handler->firstPoint).Length() < Precision::Confusion()) {
                    unsetOnViewParameter(thirdParam.get());
                    unsetOnViewParameter(fourthParam.get());
                }
            }
        } break;
        case SelectMode::SeekThird: {
            auto& fifthParam = onViewParameters[OnViewParameter::Fifth];

            if (handler->constructionMethod() == DrawSketchHandlerArc::ConstructionMethod::Center) {
                if (fifthParam->isSet) {
                    double arcAngle = Base::toRadians(fifthParam->getValue());
                    if (fmod(fabs(arcAngle), 2 * std::numbers::pi) < Precision::Confusion()
                        && fifthParam->hasFinishedEditing) {
                        unsetOnViewParameter(fifthParam.get());
                        return;
                    }

                    handler->arcAngle = arcAngle;

                    double angle = handler->startAngle + arcAngle;
                    onSketchPos.x = handler->centerPoint.x + cos(angle) * handler->radius;
                    onSketchPos.y = handler->centerPoint.y + sin(angle) * handler->radius;
                }
            }
            else {
                auto& sixthParam = onViewParameters[OnViewParameter::Sixth];
                if (fifthParam->isSet) {
                    onSketchPos.x = fifthParam->getValue();
                }

                if (sixthParam->isSet) {
                    onSketchPos.y = sixthParam->getValue();
                }
            }
        } break;
        default:
            break;
    }
}

template<>
void DSHArcController::adaptParameters(Base::Vector2d onSketchPos)
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

            if (handler->isTangent()) {
                if (!thirdParam->isSet) {
                    setOnViewParameterValue(OnViewParameter::Third, handler->radius);
                }
                if (!fourthParam->isSet) {
                    setOnViewParameterValue(
                        OnViewParameter::Fourth,
                        Base::toDegrees(handler->arcAngle),
                        Base::Unit::Angle
                    );
                }
                const Base::Vector3d center = toVector3d(handler->centerPoint);
                thirdParam->setPoints(center, toVector3d(onSketchPos));
                fourthParam->setPoints(center, Base::Vector3d());
                fourthParam->setLabelStartAngle(handler->startAngle);
                fourthParam->setLabelRange(handler->arcAngle);
                break;
            }

            if (handler->constructionMethod() == DrawSketchHandlerArc::ConstructionMethod::Center) {

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
            }
            else {
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
            }
        } break;
        case SelectMode::SeekThird: {
            auto& fifthParam = onViewParameters[OnViewParameter::Fifth];

            if (handler->constructionMethod() == DrawSketchHandlerArc::ConstructionMethod::Center) {
                double range = Base::toDegrees(handler->arcAngle);

                if (!fifthParam->isSet) {
                    setOnViewParameterValue(OnViewParameter::Fifth, range, Base::Unit::Angle);
                }

                Base::Vector3d start = toVector3d(handler->centerPoint);
                fifthParam->setPoints(start, Base::Vector3d());

                fifthParam->setLabelStartAngle(handler->startAngle);
                fifthParam->setLabelRange(handler->arcAngle);
            }
            else {
                auto& sixthParam = onViewParameters[OnViewParameter::Sixth];
                if (!fifthParam->isSet) {
                    setOnViewParameterValue(OnViewParameter::Fifth, onSketchPos.x);
                }

                if (!sixthParam->isSet) {
                    setOnViewParameterValue(OnViewParameter::Sixth, onSketchPos.y);
                }

                bool sameSign = onSketchPos.x * onSketchPos.y > 0.;
                fifthParam->setLabelAutoDistanceReverse(!sameSign);
                sixthParam->setLabelAutoDistanceReverse(sameSign);
                fifthParam->setPoints(Base::Vector3d(), toVector3d(onSketchPos));
                sixthParam->setPoints(Base::Vector3d(), toVector3d(onSketchPos));
            }
        } break;
        default:
            break;
    }
}

template<>
void DSHArcController::computeNextDrawSketchHandlerMode()
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
                handler->setNextState(handler->isTangent() ? SelectMode::End : SelectMode::SeekThird);
            }
        } break;
        case SelectMode::SeekThird: {
            auto& fifthParam = onViewParameters[OnViewParameter::Fifth];
            if (handler->constructionMethod() == DrawSketchHandlerArc::ConstructionMethod::Center) {
                if (fifthParam->hasFinishedEditing) {
                    handler->setNextState(SelectMode::End);
                }
            }
            else {
                auto& sixthParam = onViewParameters[OnViewParameter::Sixth];

                if (fifthParam->hasFinishedEditing && sixthParam->hasFinishedEditing) {
                    handler->setNextState(SelectMode::End);
                }
            }
        } break;
        default:
            break;
    }
}

template<>
void DSHArcController::addConstraints()
{
    App::DocumentObject* obj = handler->sketchgui->getObject();

    int firstCurve = handler->getHighestCurveIndex();
    using namespace Sketcher;

    auto x0 = onViewParameters[OnViewParameter::First]->getValue();
    auto y0 = onViewParameters[OnViewParameter::Second]->getValue();
    auto p3 = onViewParameters[OnViewParameter::Third]->getValue();
    auto p4 = onViewParameters[OnViewParameter::Fourth]->getValue();

    auto x0set = onViewParameters[OnViewParameter::First]->isSet;
    auto y0set = onViewParameters[OnViewParameter::Second]->isSet;
    auto p3set = onViewParameters[OnViewParameter::Third]->isSet;
    auto p4set = onViewParameters[OnViewParameter::Fourth]->isSet;
    auto p5set = onViewParameters[OnViewParameter::Fifth]->isSet;

    if (handler->isTangent()) {
        // The start is held by the tangency; a typed radius and sweep become constraints, unless the
        // end's own constraints already set them.
        bool radiusFree = true;
        if (!handler->AutoConstraints.empty()) {
            auto edgeinfo = handler->getEdgeInfo(firstCurve);
            radiusFree = static_cast<SolverGeometryExtension::Arc&>(edgeinfo).isRadiusDoF();
        }
        if (p3set && radiusFree) {
            Gui::cmdAppObjectArgs(obj, "addConstraint(Sketcher.Constraint('Radius',%d,%f)) ", firstCurve, p3);
            if (!handler->AutoConstraints.empty()) {
                handler->diagnoseWithAutoConstraints();
            }
        }
        if (p4set && handler->AutoConstraints.empty()) {
            Gui::cmdAppObjectArgs(
                obj,
                "addConstraint(Sketcher.Constraint('Angle',%d,%f)) ",
                firstCurve,
                Base::toRadians(p4)
            );
        }
        return;
    }


    PointPos pos1 = handler->constructionMethod() == DrawSketchHandlerArc::ConstructionMethod::Center
        ? PointPos::mid
        : handler->arcPos1;

    auto constraintx0 = [&]() {
        ConstraintToAttachment(GeoElementId(firstCurve, pos1), GeoElementId::VAxis, x0, obj);
    };

    auto constrainty0 = [&]() {
        ConstraintToAttachment(GeoElementId(firstCurve, pos1), GeoElementId::HAxis, y0, obj);
    };

    auto constraintp3radius = [&]() {
        Gui::cmdAppObjectArgs(
            obj,
            "addConstraint(Sketcher.Constraint('Radius',%d,%f)) ",
            firstCurve,
            fabs(p3)
        );
    };

    auto constraintp5angle = [&]() {
        Gui::cmdAppObjectArgs(
            obj,
            "addConstraint(Sketcher.Constraint('Angle',%d,%f)) ",
            firstCurve,
            fabs(handler->arcAngle)
        );
    };

    auto constraintp3x = [&]() {
        ConstraintToAttachment(GeoElementId(firstCurve, handler->arcPos2), GeoElementId::VAxis, p3, obj);
    };

    auto constraintp4y = [&]() {
        ConstraintToAttachment(GeoElementId(firstCurve, handler->arcPos2), GeoElementId::HAxis, p4, obj);
    };


    if (handler->AutoConstraints.empty()) {  // No valid diagnosis. Every constraint can be added.
        if (x0set && y0set && x0 == 0. && y0 == 0.) {
            ConstraintToAttachment(GeoElementId(firstCurve, pos1), GeoElementId::RtPnt, 0., obj);
        }
        else {
            if (x0set) {
                constraintx0();
            }

            if (y0set) {
                constrainty0();
            }
        }

        if (handler->constructionMethod() == DrawSketchHandlerArc::ConstructionMethod::Center) {
            if (p3set) {
                constraintp3radius();
            }

            if (p5set) {
                constraintp5angle();
            }
        }
        else {
            if (p3set && p4set && p3 == 0. && p4 == 0.) {
                ConstraintToAttachment(
                    GeoElementId(firstCurve, handler->arcPos2),
                    GeoElementId::RtPnt,
                    0.,
                    obj
                );
            }
            else {
                if (p3set) {
                    constraintp3x();
                }

                if (p4set) {
                    constraintp4y();
                }
            }
        }
    }
    else {  // Valid diagnosis. Must check which constraints may be added.
        auto startpointinfo = handler->getPointInfo(GeoElementId(firstCurve, pos1));

        if (x0set && startpointinfo.isXDoF()) {
            constraintx0();

            handler->diagnoseWithAutoConstraints();  // ensure we have recalculated parameters after
                                                     // each constraint addition
            // get updated point position
            startpointinfo = handler->getPointInfo(GeoElementId(firstCurve, pos1));
        }

        if (y0set && startpointinfo.isYDoF()) {
            constrainty0();

            handler->diagnoseWithAutoConstraints();  // ensure we have recalculated parameters after
                                                     // each constraint addition
            // get updated point position
            startpointinfo = handler->getPointInfo(GeoElementId(firstCurve, pos1));
        }


        if (handler->constructionMethod() == DrawSketchHandlerArc::ConstructionMethod::Center) {
            startpointinfo = handler->getPointInfo(GeoElementId(firstCurve, PointPos::start));
            auto endpointinfo = handler->getPointInfo(GeoElementId(firstCurve, PointPos::end));
            auto midpointinfo = handler->getPointInfo(GeoElementId(firstCurve, PointPos::mid));

            int DoFs = startpointinfo.getDoFs();
            DoFs += endpointinfo.getDoFs();
            DoFs += midpointinfo.getDoFs();

            if (p3set && DoFs > 0) {
                constraintp3radius();
                DoFs--;
            }

            if (p5set && DoFs > 0) {
                constraintp5angle();
            }
        }
        else {
            auto endpointinfo = handler->getPointInfo(GeoElementId(firstCurve, handler->arcPos2));

            if (p3set && endpointinfo.isXDoF()) {
                constraintp3x();

                handler->diagnoseWithAutoConstraints();  // ensure we have recalculated parameters
                                                         // after each constraint addition
                                                         // get updated point position
                startpointinfo = handler->getPointInfo(GeoElementId(firstCurve, handler->arcPos1));
                endpointinfo = handler->getPointInfo(GeoElementId(firstCurve, handler->arcPos2));
            }

            if (p4set && endpointinfo.isYDoF()) {
                constraintp4y();
            }
        }
    }
}

template<>
void DSHArcController::doConstructionMethodChanged()
{
    handler->updateHint();
}

}  // namespace SketcherGui
