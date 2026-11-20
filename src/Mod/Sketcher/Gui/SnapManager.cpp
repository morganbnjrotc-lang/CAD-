// SPDX-License-Identifier: LGPL-2.1-or-later

/***************************************************************************
 *   Copyright (c) 2023 Pierre-Louis Boyer <pierrelouis.boyer@gmail.com>   *
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

#include <QApplication>

#include <Base/Tools.h>
#include <Mod/Sketcher/App/SketchObject.h>

#include "SnapManager.h"
#include "ViewProviderSketch.h"


using namespace SketcherGui;
using namespace Sketcher;

/************************************ Attorney *******************************************/

inline int ViewProviderSketchSnapAttorney::getPreselectPoint(const ViewProviderSketch& vp)
{
    return vp.getPreselectPoint();
}

inline int ViewProviderSketchSnapAttorney::getPreselectCross(const ViewProviderSketch& vp)
{
    return vp.getPreselectCross();
}

inline int ViewProviderSketchSnapAttorney::getPreselectCurve(const ViewProviderSketch& vp)
{
    return vp.getPreselectCurve();
}

/**************************** ParameterObserver nested class *****************************/
SnapManager::ParameterObserver::ParameterObserver(SnapManager& client)
    : client(client)
{
    initParameters();
    subscribeToParameters();
}

SnapManager::ParameterObserver::~ParameterObserver()
{
    unsubscribeToParameters();
}

void SnapManager::ParameterObserver::initParameters()
{
    // static map to avoid substantial if/else branching
    //
    // key->first               => String of parameter,
    // key->second              => Update function to be called for the parameter,
    str2updatefunction = {
        {"Snap", [this](const std::string& param) { updateSnapParameter(param); }},
        {"SnapToObjects", [this](const std::string& param) { updateSnapToObjectParameter(param); }},
        {"SnapToGrid", [this](const std::string& param) { updateSnapToGridParameter(param); }},
        {"SnapAngle", [this](const std::string& param) { updateSnapAngleParameter(param); }},
    };

    for (auto& val : str2updatefunction) {
        auto string = val.first;
        auto function = val.second;

        function(string);
    }
}

void SnapManager::ParameterObserver::updateSnapParameter(const std::string& parametername)
{
    ParameterGrp::handle hGrp = getParameterGrpHandle();

    client.snapRequested = hGrp->GetBool(parametername.c_str(), true);
}

void SnapManager::ParameterObserver::updateSnapToObjectParameter(const std::string& parametername)
{
    ParameterGrp::handle hGrp = getParameterGrpHandle();

    client.snapToObjectsRequested = hGrp->GetBool(parametername.c_str(), true);
}

void SnapManager::ParameterObserver::updateSnapToGridParameter(const std::string& parametername)
{
    ParameterGrp::handle hGrp = getParameterGrpHandle();

    client.snapToGridRequested = hGrp->GetBool(parametername.c_str(), false);
}

void SnapManager::ParameterObserver::updateSnapAngleParameter(const std::string& parametername)
{
    ParameterGrp::handle hGrp = getParameterGrpHandle();

    client.snapAngle
        = fmod(Base::toRadians(hGrp->GetFloat(parametername.c_str(), 5.)), 2 * std::numbers::pi);
}

void SnapManager::ParameterObserver::subscribeToParameters()
{
    try {
        ParameterGrp::handle hGrp = getParameterGrpHandle();
        hGrp->Attach(this);
    }
    catch (const Base::ValueError& e) {  // ensure that if parameter strings are not well-formed,
                                         // the exception is not propagated
        Base::Console().developerError("SnapManager", "Malformed parameter string: {}\n", e.what());
    }
}

void SnapManager::ParameterObserver::unsubscribeToParameters()
{
    try {
        ParameterGrp::handle hGrp = getParameterGrpHandle();
        hGrp->Detach(this);
    }
    catch (const Base::ValueError& e) {  // ensure that if parameter strings are not well-formed,
                                         // the program is not terminated when calling the noexcept
                                         // destructor.
        Base::Console().developerError("SnapManager", "Malformed parameter string: {}\n", e.what());
    }
}

void SnapManager::ParameterObserver::OnChange(Base::Subject<const char*>& rCaller, const char* sReason)
{
    (void)rCaller;

    auto key = str2updatefunction.find(sReason);
    if (key != str2updatefunction.end()) {
        auto string = key->first;
        auto function = key->second;

        function(string);
    }
}

ParameterGrp::handle SnapManager::ParameterObserver::getParameterGrpHandle()
{
    return App::GetApplication().GetParameterGroupByPath(
        "User parameter:BaseApp/Preferences/Mod/Sketcher/Snap"
    );
}

//**************************** SnapManager class ******************************

SnapManager::SnapManager(ViewProviderSketch& vp)
    : viewProvider(vp)
    , angleSnapRequested(false)
    , referencePoint(Base::Vector2d(0., 0.))
    , lastMouseAngle(0.0)
{
    // Create parameter observer and initialise watched parameters
    pObserver = std::make_unique<SnapManager::ParameterObserver>(*this);
}

SnapManager::~SnapManager()
{}

Base::Vector2d SnapManager::snap(Base::Vector2d inputPos, SnapType mask)
{
    if (!snapRequested) {
        return inputPos;
    }

    Base::Vector2d snapPos = inputPos;

    // In order of priority:

    // 1 - Snap at an angle
    if ((static_cast<int>(mask) & static_cast<int>(SnapType::Angle)) && angleSnapRequested
        && QApplication::keyboardModifiers() == Qt::ControlModifier
        && snapAtAngle(inputPos, snapPos)) {
        return snapPos;
    }
    else {
        lastMouseAngle = 0.0;
    }

    // 2 - Snap to objects (may partially snap to axis, leaving other coordinate for grid)
    bool snappedToObject = false;
    if ((static_cast<int>(mask)
         & (static_cast<int>(SnapType::Point) | static_cast<int>(SnapType::Edge)))
        && snapToObjectsRequested) {
        snappedToObject = snapToObject(inputPos, snapPos, mask);
        if (snappedToObject) {
            return snapPos;  // Full snap (point or curve) - done
        }
        // if false was returned but snapPos was modified (axis case), continue to grid snap
    }

    // 3 - Snap to grid (will work on coordinates not already locked by axis snap)
    if ((static_cast<int>(mask) & static_cast<int>(SnapType::Grid)) && snapToGridRequested
        /*&& viewProvider.ShowGrid.getValue() */) {  // Snap to grid is enabled
                                                     // even if the grid is not visible.

        // use snapPos as input (which may have one coordinate locked by axis)
        Base::Vector2d gridSnapResult = snapPos;
        if (snapToGrid(snapPos, gridSnapResult)) {
            return gridSnapResult;
        }
        // if grid snap happened, return the result which combines axis + grid
        // if axis locked a coordinate, snapPos already had it, and grid snap respected it
        return snapPos;
    }

    return snapPos;
}

bool SnapManager::snapAtAngle(Base::Vector2d inputPos, Base::Vector2d& snapPos)
{
    double length = (inputPos - referencePoint).Length();

    double angle1 = (inputPos - referencePoint).Angle();
    double angle2 = angle1 + (angle1 < 0. ? 2 : -2) * std::numbers::pi;
    lastMouseAngle = abs(angle1 - lastMouseAngle) < abs(angle2 - lastMouseAngle) ? angle1 : angle2;

    double angle = round(lastMouseAngle / snapAngle) * snapAngle;
    snapPos = referencePoint + length * Base::Vector2d(cos(angle), sin(angle));

    return true;
}

bool SnapManager::snapToObject(Base::Vector2d inputPos, Base::Vector2d& snapPos, SnapType mask)
{
    Sketcher::SketchObject* Obj = viewProvider.getSketchObject();
    int geoId = GeoEnum::GeoUndef;
    Sketcher::PointPos posId = Sketcher::PointPos::none;

    int VtId = ViewProviderSketchSnapAttorney::getPreselectPoint(viewProvider);
    int CrsId = ViewProviderSketchSnapAttorney::getPreselectCross(viewProvider);
    int CrvId = ViewProviderSketchSnapAttorney::getPreselectCurve(viewProvider);

    if ((static_cast<int>(mask) & static_cast<int>(SnapType::Point)) && (CrsId == 0 || VtId >= 0)) {
        if (CrsId == 0) {
            geoId = Sketcher::GeoEnum::RtPnt;
            posId = Sketcher::PointPos::start;
        }
        else if (VtId >= 0) {
            Obj->getGeoVertexIndex(VtId, geoId, posId);
        }

        snapPos.x = Obj->getPoint(geoId, posId).x;
        snapPos.y = Obj->getPoint(geoId, posId).y;
        return true;
    }
    else if (static_cast<int>(mask) & static_cast<int>(SnapType::Edge)) {
        if (CrsId == 1 || CrsId == 2) {  // Studio: where an axis crosses a curve
            const int axis = CrsId == 1 ? GeoEnum::HAxis : GeoEnum::VAxis;
            Base::Vector3d special;
            if (snapToSpecialPoint(axis, Obj->getGeometry(axis), inputPos, special)) {
                snapPos.x = special.x;
                snapPos.y = special.y;
                return true;
            }
        }
        if (CrsId == 1) {  // H_Axis
            snapPos.y = 0;
            // dont return true, allow grid snap to handle X coordinate
            return false;
        }
        else if (CrsId == 2) {  // V_Axis
            snapPos.x = 0;
            // dont return true, allow grid snap to handle Y coordinate
            return false;
        }
        else if (CrvId >= 0 || CrvId <= Sketcher::GeoEnum::RefExt) {  // Curves

            const Part::Geometry* geo = Obj->getGeometry(CrvId);

            Base::Vector3d pointToOverride(inputPos.x, inputPos.y, 0.);

            double pointParam = 0.0;
            auto curve = dynamic_cast<const Part::GeomCurve*>(geo);
            if (curve) {
                try {
                    curve->closestParameter(pointToOverride, pointParam);
                    pointToOverride = curve->pointAtParameter(pointParam);
                }
                catch (Base::CADKernelError& e) {
                    e.reportException();
                    return false;
                }

                // Studio (PLAN 3.15): a crossing, a quadrant or a center near the pointer first
                Base::Vector3d special;
                if (snapToSpecialPoint(CrvId, geo, inputPos, special)) {
                    pointToOverride = special;
                }

                // If it is a line, then we check if we need to snap to the middle.
                else if (geo->is<Part::GeomLineSegment>()) {
                    const Part::GeomLineSegment* line = static_cast<const Part::GeomLineSegment*>(geo);
                    snapToLineMiddle(pointToOverride, line);
                }

                // If it is an arc, then we check if we need to snap to the middle (not the center).
                else if (geo->is<Part::GeomArcOfCircle>()) {
                    const Part::GeomArcOfCircle* arc = static_cast<const Part::GeomArcOfCircle*>(geo);
                    snapToArcMiddle(pointToOverride, arc);
                }

                snapPos.x = pointToOverride.x;
                snapPos.y = pointToOverride.y;

                return true;
            }
        }
    }

    // Studio: nothing under the pointer, near the center of a circle or arc whose edge was hovered
    if ((static_cast<int>(mask) & static_cast<int>(SnapType::Point)) && VtId < 0 && CrsId < 0
        && !(CrvId >= 0 || CrvId <= Sketcher::GeoEnum::RefExt)) {
        return snapToHoveredCenter(inputPos, snapPos);
    }
    return false;
}

namespace
{

// Studio (PLAN 3.15): where two lines, circles or arcs cross, analytically. A line counts as its
// segment, except the sketch's axes (unbounded); an arc as its part of the circle.
struct Shape
{
    bool round = false;
    Base::Vector2d a, b;  // a line's ends
    Base::Vector2d center;
    double radius = 0.0;
    const Part::GeomArcOfCircle* arc = nullptr;
    bool unbounded = false;
};

bool shapeOf(int geoId, const Part::Geometry* geo, Shape& shape)
{
    if (!geo) {
        return false;
    }
    if (geo->is<Part::GeomLineSegment>()) {
        auto* line = static_cast<const Part::GeomLineSegment*>(geo);
        const Base::Vector3d s = line->getStartPoint();
        const Base::Vector3d e = line->getEndPoint();
        shape.a = Base::Vector2d(s.x, s.y);
        shape.b = Base::Vector2d(e.x, e.y);
        shape.unbounded = geoId == GeoEnum::HAxis || geoId == GeoEnum::VAxis;
        return (shape.b - shape.a).Length() > Precision::Confusion();
    }
    if (geo->is<Part::GeomCircle>() || geo->is<Part::GeomArcOfCircle>()) {
        shape.round = true;
        Base::Vector3d c;
        if (geo->is<Part::GeomCircle>()) {
            auto* circle = static_cast<const Part::GeomCircle*>(geo);
            c = circle->getCenter();
            shape.radius = circle->getRadius();
        }
        else {
            shape.arc = static_cast<const Part::GeomArcOfCircle*>(geo);
            c = shape.arc->getCenter();
            shape.radius = shape.arc->getRadius();
        }
        shape.center = Base::Vector2d(c.x, c.y);
        return shape.radius > Precision::Confusion();
    }
    return false;
}

bool onShape(const Shape& shape, const Base::Vector2d& p)
{
    const double slack = 1e-9;
    if (!shape.round) {
        if (shape.unbounded) {
            return true;
        }
        const Base::Vector2d along = shape.b - shape.a;
        const double t = ((p - shape.a) * along) / (along * along);
        return t >= -slack && t <= 1 + slack;
    }
    if (!shape.arc) {
        return true;
    }
    double u, v;
    shape.arc->getRange(u, v, true);
    double angle = (p - shape.center).Angle();
    while (angle < u - slack) {
        angle += 2 * std::numbers::pi;
    }
    while (v < u) {
        v += 2 * std::numbers::pi;
    }
    return angle <= v + slack;
}

void crossings(const Shape& s1, const Shape& s2, std::vector<Base::Vector2d>& points)
{
    std::vector<Base::Vector2d> found;
    if (!s1.round && !s2.round) {
        const Base::Vector2d u = s1.b - s1.a;
        const Base::Vector2d v = s2.b - s2.a;
        const double cross = u.x * v.y - u.y * v.x;
        if (fabs(cross) < 1e-12) {
            return;  // parallel
        }
        const Base::Vector2d w = s2.a - s1.a;
        const double t = (w.x * v.y - w.y * v.x) / cross;
        found.push_back(s1.a + t * u);
    }
    else if (s1.round != s2.round) {
        const Shape& line = s1.round ? s2 : s1;
        const Shape& round = s1.round ? s1 : s2;
        const Base::Vector2d u = line.b - line.a;
        const Base::Vector2d f = line.a - round.center;
        const double a = u * u;
        const double b = 2 * (u * f);
        const double c = f * f - round.radius * round.radius;
        const double disc = b * b - 4 * a * c;
        if (disc < 0) {
            return;
        }
        for (double sign : {-1.0, 1.0}) {
            found.push_back(line.a + ((-b + sign * sqrt(disc)) / (2 * a)) * u);
        }
    }
    else {
        const Base::Vector2d between = s2.center - s1.center;
        const double d = between.Length();
        if (d < Precision::Confusion() || d > s1.radius + s2.radius
            || d < fabs(s1.radius - s2.radius)) {
            return;
        }
        const double along = (s1.radius * s1.radius - s2.radius * s2.radius + d * d) / (2 * d);
        const double h = sqrt(std::max(0.0, s1.radius * s1.radius - along * along));
        const Base::Vector2d unit = between / d;
        const Base::Vector2d foot = s1.center + along * unit;
        const Base::Vector2d across(-unit.y, unit.x);
        found.push_back(foot + h * across);
        found.push_back(foot - h * across);
    }
    for (const auto& p : found) {
        if (onShape(s1, p) && onShape(s2, p)) {
            points.push_back(p);
        }
    }
}

}  // namespace

double SnapManager::snapDistance() const
{
    return 0.5 * viewProvider.getScaleFactor();
}

bool SnapManager::passesThrough(int geoId, const Part::Geometry* geo, Base::Vector2d point, double tolerance)
{
    Shape shape;
    if (!shapeOf(geoId, geo, shape) || !onShape(shape, point)) {
        return false;
    }
    if (shape.round) {
        return fabs((point - shape.center).Length() - shape.radius) < tolerance;
    }
    const Base::Vector2d along = shape.b - shape.a;
    const Base::Vector2d off = point - shape.a;
    return fabs(along.x * off.y - along.y * off.x) / along.Length() < tolerance;
}

bool SnapManager::snapToSpecialPoint(
    int geoId,
    const Part::Geometry* geo,
    Base::Vector2d inputPos,
    Base::Vector3d& snapped
)
{
    Shape hovered;
    if (!shapeOf(geoId, geo, hovered)) {
        return false;
    }
    if (hovered.round) {  // remembered: its center snaps for a while (snapToHoveredCenter)
        std::erase(hoveredCircles, geoId);
        hoveredCircles.insert(hoveredCircles.begin(), geoId);
        if (hoveredCircles.size() > 6) {
            hoveredCircles.pop_back();
        }
    }

    std::vector<Base::Vector2d> candidates;
    if (hovered.round) {  // quadrants
        for (int quarter = 0; quarter < 4; ++quarter) {
            const double angle = quarter * std::numbers::pi / 2;
            const Base::Vector2d p = hovered.center + hovered.radius * Base::Vector2d(cos(angle), sin(angle));
            if (onShape(hovered, p)) {
                candidates.push_back(p);
            }
        }
    }

    Sketcher::SketchObject* sketch = viewProvider.getSketchObject();
    auto consider = [&](int otherId) {
        if (otherId == geoId) {
            return;
        }
        Shape other;
        if (shapeOf(otherId, sketch->getGeometry(otherId), other)) {
            crossings(hovered, other, candidates);
        }
    };
    consider(GeoEnum::HAxis);
    consider(GeoEnum::VAxis);
    for (int id = 0; id <= sketch->getHighestCurveIndex(); ++id) {
        consider(id);
    }
    for (int i = 0; i < sketch->getExternalGeometryCount(); ++i) {
        consider(GeoEnum::RefExt - i);
    }
    for (int circleId : hoveredCircles) {  // the centers of circles hovered lately
        Shape circle;
        if (circleId != geoId && shapeOf(circleId, sketch->getGeometry(circleId), circle) && circle.round) {
            candidates.push_back(circle.center);
        }
    }

    double best = snapDistance();
    bool found = false;
    for (const auto& p : candidates) {
        const double distance = (p - inputPos).Length();
        if (distance < best) {
            best = distance;
            snapped = Base::Vector3d(p.x, p.y, 0.);
            found = true;
        }
    }
    return found;
}

bool SnapManager::snapToHoveredCenter(Base::Vector2d inputPos, Base::Vector2d& snapPos)
{
    Sketcher::SketchObject* sketch = viewProvider.getSketchObject();
    // Twice as far as other snaps: finding a center is the point, and FreeCAD's own pick of the
    // center dot reaches about 8 pixels already.
    double best = 2 * snapDistance();
    bool found = false;
    for (int circleId : hoveredCircles) {
        Shape circle;
        if (!shapeOf(circleId, sketch->getGeometry(circleId), circle) || !circle.round) {
            continue;
        }
        const double distance = (circle.center - inputPos).Length();
        if (distance < best) {
            best = distance;
            snapPos = circle.center;
            found = true;
        }
    }
    return found;
}

bool SnapManager::snapToGrid(Base::Vector2d inputPos, Base::Vector2d& snapPos)
{
    // Snap Tolerance in pixels
    const double snapTol = viewProvider.getGridSize() / 5;

    snapPos = inputPos;

    double tmpX = inputPos.x, tmpY = inputPos.y;

    viewProvider.getClosestGridPoint(tmpX, tmpY);

    bool snapped = false;

    // Check if x within snap tolerance
    if (inputPos.x < tmpX + snapTol && inputPos.x > tmpX - snapTol) {
        snapPos.x = tmpX;  // Snap X Mouse Position
        snapped = true;
    }

    // Check if y within snap tolerance
    if (inputPos.y < tmpY + snapTol && inputPos.y > tmpY - snapTol) {
        snapPos.y = tmpY;  // Snap Y Mouse Position
        snapped = true;
    }

    return snapped;
}

bool SnapManager::snapToLineMiddle(Base::Vector3d& pointToOverride, const Part::GeomLineSegment* line)
{
    Base::Vector3d startPoint = line->getStartPoint();
    Base::Vector3d endPoint = line->getEndPoint();
    Base::Vector3d midPoint = (startPoint + endPoint) / 2;

    // Check if we are at middle of the line and if so snap to it. Studio (PLAN 3.15): easier to
    // catch than 5 % of the length: the snap distance, or 10 %, up to a fifth of the line.
    const double length = (endPoint - startPoint).Length();
    const double zone = std::min(std::max(0.1 * length, snapDistance()), 0.2 * length);
    if ((pointToOverride - midPoint).Length() < zone) {
        pointToOverride = midPoint;
        return true;
    }

    return false;
}

bool SnapManager::snapToArcMiddle(Base::Vector3d& pointToOverride, const Part::GeomArcOfCircle* arc)
{
    Base::Vector3d centerPoint = arc->getCenter();
    Base::Vector3d startVec = (arc->getStartPoint() - centerPoint);
    Base::Vector3d middleVec = startVec + (arc->getEndPoint() - centerPoint);

    /* Handle the case of arc angle = 180 */
    if (middleVec.Length() < Precision::Confusion()) {
        middleVec.x = startVec.y;
        middleVec.y = -startVec.x;
    }
    else {
        middleVec = middleVec / middleVec.Length() * arc->getRadius();
    }

    Base::Vector2d mVec = Base::Vector2d(middleVec.x, middleVec.y);
    Base::Vector3d pointVec = pointToOverride - centerPoint;
    Base::Vector2d pVec = Base::Vector2d(pointVec.x, pointVec.y);

    double u, v;
    arc->getRange(u, v, true);
    if (v < u) {
        v += 2 * std::numbers::pi;
    }
    double angle = v - u;
    int revert = angle < std::numbers::pi ? 1 : -1;

    /*To know if we are close to the middle of the arc, we are going to compare the angle of the
     * (mouse cursor - center) to the angle of the middle of the arc. If it's less than 10% of the
     * arc angle, then we snap.
     */
    // Studio (PLAN 3.15): at least the snap distance along the arc, up to a fifth of it.
    const double zone = std::min(std::max(0.10 * angle, snapDistance() / arc->getRadius()), 0.2 * angle);
    if (fabs(pVec.Angle() - (revert * mVec).Angle()) < zone) {
        pointToOverride = centerPoint + middleVec * revert;
        return true;
    }

    return false;
}

void SnapManager::setAngleSnapping(bool enable, Base::Vector2d referencepoint)
{
    angleSnapRequested = enable;
    referencePoint = referencepoint;
}

Base::Vector2d SketcherGui::SnapManager::SnapHandle::compute(SnapType mask)
{
    if (!mgr) {
        return cursorPos;
    }
    return mgr->snap(cursorPos, mask);
}
