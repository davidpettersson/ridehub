Feature: Event Capacity

  Scenario: No limit set
    Given an event
      And the event registration limit is empty
      And the event has 1 registration
    When visiting the event detail page
    Then the event shows 1 registered

  Scenario: Limit two, zero registration
    Given an event
      And the event registration limit is 2
      And the event has 0 registration
    When visiting the event detail page
    Then the event does not show registrations

  Scenario: Limit two, one registration
    Given an event
      And the event registration limit is 2
      And the event has 1 registration
    When visiting the event detail page
    Then the event shows 1/2 registered

  Scenario: Limit two, two registrations
    Given an event
      And the event registration limit is 2
      And the event has 2 registration
    When visiting the event detail page
    Then the event shows 2/2 registered

  Scenario: Limit two, three registrations
    Given an event
      And the event registration limit is 2
      And the event has 3 registration
    When visiting the event detail page
    Then the event shows 3/2 registered

  Scenario: External registration has no count
    Given an event
      And the event has external registration
    When visiting the event detail page
    Then the event does not show registrations
