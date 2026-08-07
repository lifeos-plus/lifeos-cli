import React from "react";
import type { PersonSummary } from "@/services/api";
import { Icon } from "./icons";
import Badge from "./common/Badge";

interface PersonsListProps {
  people?: PersonSummary[] | null;
  className?: string;
  inline?: boolean; // inline pill style vs stacked rows
  showIcon?: boolean; // show leading icon
  max?: number; // maximum persons to render; overflow aggregated as +X
  renderItem?: (person: PersonSummary) => React.ReactNode; // override item render
  emptyText?: string; // displayed when persons empty
}

const PersonsListComponent: React.FC<PersonsListProps> = ({
  people,
  className,
  inline = false,
  showIcon = true,
  max,
  renderItem,
  emptyText = "-",
}) => {
  const list = Array.isArray(people) ? people : [];
  if (list.length === 0) {
    return (
      <span
        className={["text-base text-base-content/50", className || ""]
          .filter(Boolean)
          .join(" ")}
      >
        {emptyText}
      </span>
    );
  }

  const toRender =
    typeof max === "number" && max >= 0 ? list.slice(0, max) : list;
  const overflow = list.length - toRender.length;

  if (inline) {
    return (
      <div
        className={["flex items-center flex-wrap gap-1", className || ""]
          .filter(Boolean)
          .join(" ")}
      >
        {toRender.map((person) => (
          <Badge
            key={person.id}
            tone="neutral"
            variant="outline"
            size="sm"
            className="gap-1 bg-base-100"
            title={person.display_name ?? person.name ?? ""}
          >
            {showIcon ? (
              <Icon
                name="people"
                size={16}
                aria-hidden
                className="text-primary"
              />
            ) : null}
            {renderItem
              ? renderItem(person)
              : (person.display_name ?? person.name ?? "")}
          </Badge>
        ))}
        {overflow > 0 ? <span className="text-sm">+{overflow}</span> : null}
      </div>
    );
  }

  return (
    <div className={["text-sm", className || ""].filter(Boolean).join(" ")}>
      {toRender.map((person) => (
        <div key={person.id} className="flex items-center">
          {showIcon ? (
            <Icon
              name="people"
              size={16}
              aria-hidden
              className="text-primary mr-1"
            />
          ) : null}
          <span className="text-sm">
            {renderItem
              ? renderItem(person)
              : (person.display_name ?? person.name ?? "")}
          </span>
        </div>
      ))}
      {overflow > 0 ? <div className="text-sm">+{overflow}</div> : null}
    </div>
  );
};

const PersonsList = React.memo(PersonsListComponent, (prev, next) => {
  const prevIds = (prev.people || []).map((p) => p.id).join(",");
  const nextIds = (next.people || []).map((p) => p.id).join(",");
  return (
    prevIds === nextIds &&
    prev.className === next.className &&
    prev.inline === next.inline &&
    prev.showIcon === next.showIcon &&
    prev.max === next.max &&
    prev.emptyText === next.emptyText &&
    prev.renderItem === next.renderItem
  );
});

export default PersonsList;
