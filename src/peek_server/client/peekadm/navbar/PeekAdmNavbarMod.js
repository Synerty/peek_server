/// <amd-dependency path="angular"/>

'use strict';

define([
    // Named Dependencies
    "AngFormLoadController",
    // Unnamed Dependencies
    "angular", "jquery"], function (AngFormLoadController) {
// -------------------------- Navbar Module -----------------------
    var peekAdmNavbarMod = angular.module('peekAdmNavbarMod', []);

// ------ BuildNavbarCtrl
    peekAdmNavbarMod.controller('PeekAdmNavbarCtrl', [
        '$scope',
        '$location',
        function ($scope, $location) {
            var self = this;

            var s = $scope;
            $scope.wereAt = function (path) {
                return $location.absUrl().endsWith(path)
                        || ($location.path().startsWith(path) && !$location.path().startsWith(path + '/'));
            };

            new AngFormLoadController($scope,
                    {
                        papp: 'platform',
                        key: "peekadm.navbar.data"
                    }, {
                        objName: "navData"
                    }
            );

        }]);

// Add custom directive for peek_server-navbar
    peekAdmNavbarMod.directive('peekAdmNavbar', function () {
        return {
            restrict: 'E',
            templateUrl: '/view/PeekAdmNavbarView.html'
        };
    });

});